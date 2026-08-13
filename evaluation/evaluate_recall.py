"""Đánh giá Dense Retriever bằng Recall@K trên tập dev set.

Script này đọc file JSON dev_set.json, chạy từng câu hỏi qua pipeline Dense Retrieval
hiện có trong repo, và tính các metric Recall@1, Recall@3, Recall@5, Recall@10.

Mỗi câu hỏi có thể có nhiều gold_ids; do đó, Recall@K được tính theo công thức:
    |Gold ∩ TopK| / |Gold|

không phải chỉ cần có ít nhất một gold hit là 1.0.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

import config
from evaluation.metrics import recall_at_k
from ingestion.chunker import parse_law_text
from ingestion.metadata import attach_effective_metadata, load_law_meta
from retrieval.embedder import get_embedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import retrieve

SOURCE_URL = (
    "https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-67-vbhn-vpqh-469197.htm"
)
K_VALUES = [1, 3, 5, 10]
DEFAULT_DEV_SET_PATH = Path("data/evaluation/dev_set.json")
DEFAULT_RESULTS_PATH = Path("evaluation/recall_results.json")


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


def build_provisions() -> list:
    """Build corpus từ văn bản pháp luật theo pipeline hiện có trong repo."""
    raw_path = config.DATA_RAW_DIR / "67-VBHN-VPQH.txt"
    if not raw_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file văn bản raw: {raw_path}")

    text = raw_path.read_text(encoding="utf-8")
    provisions = parse_law_text(
        text,
        law_code=config.LAW_CODE,
        source_url=SOURCE_URL,
    )
    law_meta = load_law_meta(raw_path)
    provisions = attach_effective_metadata(provisions, law_meta)
    return provisions


def build_dense_index(provisions: list) -> tuple[object, FaissFlatIndex]:
    """Khởi tạo embedder và FAISS cho toàn bộ corpus."""
    embedder = get_embedder()
    texts = [p.text for p in provisions]
    vectors = embedder.encode(texts)

    faiss_index = FaissFlatIndex(vectors.shape[1])
    faiss_index.add(np.asarray(vectors), [p.provision_id for p in provisions])
    return embedder, faiss_index


def evaluate_one_query(
    item: dict[str, Any],
    provisions: list,
    embedder: object,
    faiss_index: FaissFlatIndex,
    k_values: list[int] = K_VALUES,
) -> dict[str, Any]:
    """Đánh giá một câu hỏi trong dev set bằng Dense Retriever.

    Các câu hỏi nhóm 4/5 có thể không có gold_ids (distractor/no-answer). Chúng vẫn
    được giữ lại trong dữ liệu đầu vào để audit, nhưng không được đếm vào trung bình
    Recall@K vì không có mục tiêu đúng nào để hit.
    """
    question = str(item["question"]).strip()
    gold_ids = [str(g).strip() for g in item.get("gold_ids", []) if str(g).strip()]

    hits = retrieve(
        query=question,
        provisions=provisions,
        embedder=embedder,
        faiss_index=faiss_index,
        top_k=max(k_values),
    )

    retrieved_ids = [hit.provision.provision_id for hit in hits]
    result = {
        "id": str(item["id"]),
        "group": str(item.get("group", "")),
        "question": question,
        "gold_ids": gold_ids,
        "retrieved_ids": retrieved_ids,
        "is_valid_for_recall": bool(gold_ids),
    }

    for k in k_values:
        result[f"recall_at_{k}"] = recall_at_k(gold_ids, retrieved_ids, k)

    return result


def _is_summary_group(item: dict[str, Any]) -> bool:
    """Chỉ tính Recall cho các câu hỏi thuộc Nhóm 1–3.

    Nhóm 4 và 5 là tập nhiễu / phản biện không có gold_ids, nên không tính vào trung bình Recall@K.
    """
    group = str(item.get("group", "")).strip().lower()
    return group in {"nhóm 1", "nhom 1", "nhóm 2", "nhom 2", "nhóm 3", "nhom 3"}


def compute_summary(results: list[dict[str, Any]], k_values: list[int] = K_VALUES) -> dict[str, Any]:
    """Tính mean Recall@K chỉ trên các query thuộc nhóm đánh giá chính (1–3)."""
    summary: dict[str, Any] = {}
    valid_queries = [
        r for r in results if r.get("is_valid_for_recall") and _is_summary_group(r)
    ]
    excluded_queries = len(results) - len(valid_queries)

    for k in k_values:
        values = [r.get(f"recall_at_{k}", np.nan) for r in valid_queries]
        summary[f"recall_at_{k}"] = float(np.nanmean(values)) if values else float("nan")

    summary["num_queries"] = len(results)
    summary["num_valid_queries"] = len(valid_queries)
    summary["num_excluded_queries"] = excluded_queries
    summary["num_no_gold_queries"] = sum(
        1 for r in results if not r.get("is_valid_for_recall")
    )
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
    print("Recall@K Evaluation")
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
        description="Đánh giá Dense Retriever trên dev set bằng Recall@K."
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
    provisions = build_provisions()
    embedder, faiss_index = build_dense_index(provisions)

    results: list[dict[str, Any]] = []
    for item in dev_items:
        record = evaluate_one_query(item, provisions, embedder, faiss_index, K_VALUES)
        results.append(record)

    summary = compute_summary(results, K_VALUES)
    save_results(results, summary, output_path)
    print_summary(summary)

    print(f"Saved results to: {output_path}")


if __name__ == "__main__":
    main()
