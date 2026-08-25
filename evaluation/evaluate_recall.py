"""Đánh giá Dense Retriever bằng Recall@K trên tập dev set.

Script này đọc file JSON dev_set.json, chạy từng câu hỏi qua pipeline Dense Retrieval
hiện có trong repo, và tính các metric Recall@1, Recall@3, Recall@5, Recall@10, Recall@20.

Granularity-aware Recall:
- gold = ArtX       → HIT chỉ khi retrieved đủ TẤT CẢ child chunks của Điều X
                       (hoặc đúng chunk ArtX nếu corpus có sẵn chunk đó).
- gold = ArtX_KhY  → HIT chỉ khi retrieved đúng ArtX_KhY (exact-match).

Recall@K = số gold targets được retrieve đúng / tổng số gold targets.
"""

from __future__ import annotations

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from pipeline import RAGPipeline
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import retrieve

K_VALUES = [1, 3, 5, 10]
DEFAULT_DEV_SET_PATH = Path("data/evaluation/dev_set.json")
DEFAULT_RESULTS_PATH = Path("evaluation/recall_results.json")

# Regex phân biệt ID cấp Điều (ArtX) và cấp Khoản (ArtX_KhY / ArtX_KhY.Z)
_CLAUSE_SUFFIX_RE = re.compile(r"_Kh\w+$", re.IGNORECASE)


def load_dev_set(path: Path) -> list[dict[str, Any]]:
    """Đọc dev_set.json và validate schema đầu vào."""
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file dev set: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Dev set phải là một list JSON, nhưng nhận được {type(data).__name__}.")

    for idx, item in enumerate(data):
        missing = [key for key in ("id", "group", "question", "gold_ids") if key not in item]
        if missing:
            raise ValueError(f"Record #{idx} thiếu các trường bắt buộc: {missing}")

        if not isinstance(item["gold_ids"], list):
            raise ValueError(f"Record '{item.get('id', idx)}' có gold_ids không phải list.")

    return data


def _is_article_level(provision_id: str) -> bool:
    """Kiểm tra xem ID có phải cấp Điều (không có đuôi _KhY) hay không."""
    return not bool(_CLAUSE_SUFFIX_RE.search(provision_id))


def build_article_children_map(provision_ids: set[str]) -> dict[str, list[str]]:
    """Xây dựng mapping từ ID cấp Điều → danh sách các child chunk trong corpus.

    Ví dụ:
        "67-VBHN-VPQH_Art22" → ["67-VBHN-VPQH_Art22_Kh1", "67-VBHN-VPQH_Art22_Kh2", ...]
    """
    children_map: dict[str, list[str]] = {}
    for pid in provision_ids:
        if not _is_article_level(pid):
            # ArtX_KhY → parent là ArtX
            parent = _CLAUSE_SUFFIX_RE.sub("", pid)
            children_map.setdefault(parent, []).append(pid)
    return children_map


def resolve_gold(
    gold_id: str,
    valid_ids: set[str],
    children_map: dict[str, list[str]],
) -> dict[str, Any]:
    """Phân tích một gold_id và trả về metadata để tính HIT.

    Returns dict với các trường:
        gold_id      : ID gốc từ dev_set
        level        : "article" | "clause"
        required_chunks : tập các chunk cần có trong Top-K để tính HIT
        resolvable   : True nếu gold_id có thể được resolve từ corpus
    """
    is_article = _is_article_level(gold_id)

    if not is_article:
        # Cấp Khoản: yêu cầu exact-match
        return {
            "gold_id": gold_id,
            "level": "clause",
            "required_chunks": [gold_id],
            "resolvable": gold_id in valid_ids,
        }

    # Cấp Điều: ưu tiên chunk parent nếu có, fallback sang children
    if gold_id in valid_ids:
        return {
            "gold_id": gold_id,
            "level": "article",
            "required_chunks": [gold_id],
            "resolvable": True,
        }

    children = children_map.get(gold_id, [])
    if children:
        return {
            "gold_id": gold_id,
            "level": "article",
            "required_chunks": sorted(children),
            "resolvable": True,
        }

    # Không tồn tại trong corpus và không có children
    return {
        "gold_id": gold_id,
        "level": "article",
        "required_chunks": [],
        "resolvable": False,
    }


def is_gold_hit(resolution: dict[str, Any], retrieved_top_k: set[str]) -> bool:
    """Kiểm tra xem một gold target có được retrieve đúng trong Top-K không.

    - Cấp Khoản: phải exact-match (required_chunks có đúng 1 phần tử).
    - Cấp Điều: phải retrieve ĐỦ tất cả required_chunks (toàn bộ children).
    """
    required = resolution["required_chunks"]
    if not required:
        return False
    return all(r in retrieved_top_k for r in required)


def granularity_recall_at_k(
    gold_ids: list[str],
    retrieved_ids: list[str],
    k: int,
    valid_ids: set[str],
    children_map: dict[str, list[str]],
) -> tuple[float, list[dict[str, Any]]]:
    """Tính Recall@K theo granularity và trả về cả gold_resolution để audit.

    Returns:
        (recall_score, gold_resolution_list)
    """
    if not gold_ids:
        return 0.0, []

    retrieved_top_k = set(retrieved_ids[:k])
    resolutions = []
    hits = 0

    for gid in gold_ids:
        res = resolve_gold(gid, valid_ids, children_map)
        hit = is_gold_hit(res, retrieved_top_k)
        resolutions.append({**res, "matched": hit})
        if hit:
            hits += 1

    return hits / len(gold_ids), resolutions


def _is_summary_group(item: dict[str, Any]) -> bool:
    """Chỉ tính Recall cho các câu hỏi thuộc Nhóm 1–3.

    Nhóm 4 và 5 là tập nhiễu / phản biện không có gold_ids, nên không tính vào trung bình Recall@K.
    """
    group = str(item.get("group", "")).strip().lower()
    return group in {"nhóm 1", "nhom 1", "nhóm 2", "nhom 2", "nhóm 3", "nhom 3"}


def evaluate_one_query(
    item: dict[str, Any],
    provisions: list,
    embedder: object,
    faiss_index: FaissFlatIndex,
    valid_ids: set[str],
    children_map: dict[str, list[str]],
    k_values: list[int] = K_VALUES,
) -> dict[str, Any]:
    """Đánh giá một câu hỏi trong dev set bằng Dense Retriever (granularity-aware).

    Các câu hỏi nhóm 4/5 được giữ lại trong dữ liệu đầu vào để audit, nhưng không
    được đếm vào trung bình Recall@K vì không có mục tiêu đúng nào để hit.
    """
    question = str(item["question"]).strip()
    gold_ids = [str(g).strip() for g in item.get("gold_ids", []) if str(g).strip()]
    is_valid_for_recall = _is_summary_group(item)

    hits = retrieve(
        query=question,
        provisions=provisions,
        embedder=embedder,
        faiss_index=faiss_index,
        top_k=max(k_values),
    )

    retrieved_ids = [hit.provision.provision_id for hit in hits]

    result: dict[str, Any] = {
        "id": str(item["id"]),
        "group": str(item.get("group", "")),
        "question": question,
        "gold_ids": gold_ids,
        "retrieved_ids": retrieved_ids,
        "is_valid_for_recall": is_valid_for_recall,
    }

    if is_valid_for_recall:
        # Tính granularity recall; gold_resolution được lấy từ lần chạy k lớn nhất
        gold_resolution = None
        for k in k_values:
            score, resolutions = granularity_recall_at_k(
                gold_ids, retrieved_ids, k, valid_ids, children_map
            )
            result[f"recall_at_{k}"] = score
            if gold_resolution is None:
                # Lưu resolution của k lớn nhất để audit (sẽ bị ghi đè đến k cuối)
                gold_resolution = resolutions
        result["gold_resolution"] = gold_resolution
    else:
        for k in k_values:
            result[f"recall_at_{k}"] = None
        result["gold_resolution"] = None

    return result


def compute_summary(results: list[dict[str, Any]], k_values: list[int] = K_VALUES) -> dict[str, Any]:
    """Tính mean Recall@K chỉ trên các query thuộc nhóm đánh giá chính (1–3)."""
    summary: dict[str, Any] = {}
    valid_queries = [r for r in results if r.get("is_valid_for_recall")]
    excluded_queries = len(results) - len(valid_queries)

    for k in k_values:
        values = [r.get(f"recall_at_{k}") for r in valid_queries if r.get(f"recall_at_{k}") is not None]
        summary[f"recall_at_{k}"] = float(np.nanmean(values)) if values else float("nan")

    summary["num_queries"] = len(results)
    summary["num_valid_queries"] = len(valid_queries)
    summary["num_excluded_queries"] = excluded_queries
    summary["num_no_gold_queries"] = sum(1 for r in results if not r.get("is_valid_for_recall"))
    return summary


def save_results(results: list[dict[str, Any]], summary: dict[str, Any], output_path: Path) -> None:
    """Lưu JSON kết quả đánh giá: danh sách từng query + summary."""
    payload = {
        "results": results,
        "summary": summary,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def print_summary(summary: dict[str, Any]) -> None:
    """In ra thống kê Recall@K theo format yêu cầu."""
    print("========================================")
    print("Recall@K Evaluation (Granularity-Aware)")
    print("========================================")
    print(f"Dev set size: {summary['num_queries']}")
    print(f"Included in summary (Nhóm 1-3): {summary['num_valid_queries']}")
    print(f"Excluded from summary (Nhóm 4-5 + no-gold): {summary['num_excluded_queries']}")
    print(f"No-gold queries: {summary['num_no_gold_queries']}")
    for k in K_VALUES:
        value = summary[f"recall_at_{k}"]
        print(f"Recall@{k:>2}  : {value:.4f}")
    print("========================================")


def parse_args() -> argparse.Namespace:
    """Phân tích tham số dòng lệnh nếu người dùng muốn override path mặc định."""
    parser = argparse.ArgumentParser(
        description="Đánh giá Dense Retriever trên dev set bằng Recall@K (granularity-aware)."
    )
    parser.add_argument(
        "--dev-set",
        type=Path,
        default=DEFAULT_DEV_SET_PATH,
        help="Đường dẫn tới dev_set.json (mặc định: data/evaluation/dev_set.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_RESULTS_PATH,
        help="Đường dẫn file JSON lưu kết quả (mặc định: evaluation/recall_results.json)",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point chính."""
    args = parse_args()
    dev_set_path = args.dev_set
    output_path = args.output

    dev_items = load_dev_set(dev_set_path)

    print("Đang load chunks.jsonl và faiss.index từ production pipeline...")
    rag_pipeline = RAGPipeline()
    provisions = rag_pipeline.provisions
    embedder = rag_pipeline.embedder
    faiss_index = rag_pipeline.faiss_index

    valid_ids: set[str] = {p.provision_id for p in provisions}
    children_map = build_article_children_map(valid_ids)

    # Validate gold IDs — chỉ warning nếu không có cả parent lẫn children trong corpus
    for item in dev_items:
        for gid in item.get("gold_ids", []):
            gid = str(gid).strip()
            if not gid:
                continue
            if gid in valid_ids:
                continue  # Exact match → OK
            if _is_article_level(gid) and children_map.get(gid):
                continue  # Article-level nhưng có children → OK
            print(
                f"WARNING: gold_id '{gid}' trong câu hỏi '{item.get('id', 'unknown')}' "
                f"không tồn tại trong production chunks và không có child chunk nào."
            )

    results: list[dict[str, Any]] = []
    for item in dev_items:
        record = evaluate_one_query(
            item, provisions, embedder, faiss_index,
            valid_ids, children_map, K_VALUES
        )
        results.append(record)

    summary = compute_summary(results, K_VALUES)
    save_results(results, summary, output_path)
    print_summary(summary)
    print(f"Saved results to: {output_path}")


if __name__ == "__main__":
    main()
