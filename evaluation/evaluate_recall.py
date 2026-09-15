"""
Đánh giá độ chính xác truy hồi và hiệu quả của bộ lọc từ chối
trên tập câu hỏi kiểm thử chuẩn.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Thiết lập mã hóa UTF-8 cho Windows console
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"

import config
from ingestion.chunker import Provision
from retrieval.bm25_index import Bm25Index
from retrieval.embedder import get_embedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import retrieve, retrieve_bm25, retrieve_hybrid
from generation.refusal_gate import decide


def to_article_id(pid: str) -> str:
    """Lấy mã định danh cấp Điều từ mã khoản."""
    match = re.search(r"^(.+?_Art\d+[a-zA-Z]?)", pid)
    return match.group(1) if match else pid


def load_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    """Đọc dữ liệu câu hỏi kiểm thử từ file json."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "questions" in data:
        return data["questions"]
    if isinstance(data, list):
        return data
    raise ValueError("Định dạng file dev_set không hợp lệ.")


def load_corpus(chunks_path: Path) -> list[Provision]:
    """Nạp danh sách các đoạn luật từ file chunks.jsonl."""
    if not chunks_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {chunks_path}")

    with open(chunks_path, "r", encoding="utf-8") as f:
        return [Provision(**json.loads(line)) for line in f if line.strip()]


def evaluate_system(
    questions: list[dict[str, Any]],
    provisions: list[Provision],
    embedder: Any,
    faiss_index: FaissFlatIndex,
    bm25_index: Bm25Index,
    k_values: list[int] = [1, 3, 5, 10],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Đánh giá chất lượng truy hồi và cổng từ chối trên toàn bộ tập câu hỏi."""
    modes = ["Dense (FAISS)", "Sparse (BM25)", "Hybrid (Adaptive 3-Way RRF)"]
    
    # Khởi tạo bộ đếm kết quả cho các câu hỏi hợp lệ
    results_by_mode: dict[str, dict[str, Any]] = {
        m: {
            "hits": {k: 0 for k in k_values},
            "article_hits": {k: 0 for k in k_values},
        }
        for m in modes
    }

    in_scope_questions = [q for q in questions if q.get("expected_behavior", "answer") == "answer" or q.get("scope") == "in_scope"]
    out_of_scope_questions = [q for q in questions if q.get("expected_behavior") == "refuse" or q.get("scope") == "out_of_scope"]

    in_scope_total = len(in_scope_questions)
    out_of_scope_total = len(out_of_scope_questions)

    refusal_correct = 0
    false_refusal_count = 0
    detailed_records: list[dict[str, Any]] = []

    for q in questions:
        qid = q.get("id", "")
        q_group = q.get("group", "")
        query_text = q.get("question", "")
        scope = q.get("scope", "in_scope")
        expected_behavior = q.get("expected_behavior", "answer")
        gold_ids = q.get("gold_ids", [])
        gold_articles = {to_article_id(gid) for gid in gold_ids}

        # 1. Tìm kiếm bằng Vector (Dense)
        dense_hits = retrieve(query_text, provisions, embedder, faiss_index, top_k=max(k_values))
        dense_pids = [h.provision.provision_id for h in dense_hits]

        # 2. Tìm kiếm bằng Từ khóa (BM25)
        bm25_hits = retrieve_bm25(query_text, provisions, bm25_index, top_k=max(k_values))
        bm25_pids = [h.provision.provision_id for h in bm25_hits]

        # 3. Tìm kiếm kết hợp (Hybrid RRF)
        hybrid_hits = retrieve_hybrid(
            query=query_text,
            provisions=provisions,
            embedder=embedder,
            faiss_index=faiss_index,
            bm25_index=bm25_index,
            top_k=max(k_values),
            candidate_pool_size=config.CANDIDATE_POOL_SIZE,
            rrf_k=config.RRF_K,
            min_dense_score=config.MIN_SCORE_TIN_CAY,
        )
        hybrid_pids = [h.provision.provision_id for h in hybrid_hits]

        # Kiểm tra điều kiện từ chối trên kết quả tìm kiếm kết hợp
        gate_decision = decide(query_text, hybrid_hits)
        is_refused = gate_decision.should_refuse

        if expected_behavior == "answer":
            if is_refused:
                false_refusal_count += 1

            mode_pids = {
                "Dense (FAISS)": dense_pids,
                "Sparse (BM25)": bm25_pids,
                "Hybrid (Adaptive 3-Way RRF)": hybrid_pids,
            }

            for m, pids in mode_pids.items():
                for k in k_values:
                    # Kiểm tra trúng Khoản luật
                    if bool(set(pids[:k]) & set(gold_ids)):
                        results_by_mode[m]["hits"][k] += 1
                    # Kiểm tra trúng Điều luật
                    if bool(set(to_article_id(p) for p in pids[:k]) & gold_articles):
                        results_by_mode[m]["article_hits"][k] += 1

        elif expected_behavior == "refuse":
            if is_refused:
                refusal_correct += 1

        record = {
            "id": qid,
            "group": q_group,
            "question": query_text,
            "scope": scope,
            "expected_behavior": expected_behavior,
            "gold_ids": gold_ids,
            "is_refused": is_refused,
            "refusal_reason": gate_decision.reason,
            "dense_top5": dense_pids[:5],
            "bm25_top5": bm25_pids[:5],
            "hybrid_top5": hybrid_pids[:5],
        }
        detailed_records.append(record)

    # Tổng hợp chỉ số
    summary = {
        "total_questions": len(questions),
        "in_scope_total": in_scope_total,
        "out_of_scope_total": out_of_scope_total,
        "modes": {},
        "refusal_gate": {
            "true_refusal_rate": round((refusal_correct / out_of_scope_total * 100), 2) if out_of_scope_total > 0 else 0.0,
            "false_refusal_rate": round((false_refusal_count / in_scope_total * 100), 2) if in_scope_total > 0 else 0.0,
            "false_acceptance_rate": round(((out_of_scope_total - refusal_correct) / out_of_scope_total * 100), 2) if out_of_scope_total > 0 else 0.0,
            "refusal_precision": f"{refusal_correct}/{out_of_scope_total}",
            "false_refusal_count": f"{false_refusal_count}/{in_scope_total}",
        },
        "system_accuracy": round((refusal_correct + (results_by_mode["Hybrid (Adaptive 3-Way RRF)"]["hits"][5] - false_refusal_count)) / len(questions) * 100, 2),
    }

    for m in modes:
        mode_summary = {}
        for k in k_values:
            val = results_by_mode[m]["hits"][k] / in_scope_total if in_scope_total > 0 else 0.0
            art_val = results_by_mode[m]["article_hits"][k] / in_scope_total if in_scope_total > 0 else 0.0
            mode_summary[f"Recall@{k}"] = val
            mode_summary[f"Hit@{k}"] = val
            mode_summary[f"Article_Recall@{k}"] = art_val
        summary["modes"][m] = mode_summary

    return summary, detailed_records


def print_summary_table(summary: dict[str, Any]) -> None:
    """In bảng tổng kết kết quả đánh giá ra màn hình."""
    in_total = summary["in_scope_total"]
    print("\n" + "=" * 90)
    print(f"             BẢNG ĐÁNH GIÁ HIỆU NĂNG TRUY HỒI VÀ BỘ LỌC TỪ CHỐI")
    print("=" * 90)

    print(f"\n1. So sánh các phương pháp truy hồi ({in_total} câu hợp lệ):")
    header = f"{'Phương pháp':<28} | {'Recall@1':<10} | {'Recall@3':<10} | {'Recall@5':<10} | {'Recall@10':<10} | {'Article@5':<10}"
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    for mode, metrics in summary["modes"].items():
        rec1 = f"{metrics['Recall@1'] * 100:.2f}%"
        rec3 = f"{metrics['Recall@3'] * 100:.2f}%"
        rec5 = f"{metrics['Recall@5'] * 100:.2f}%"
        rec10 = f"{metrics['Recall@10'] * 100:.2f}%"
        art5 = f"{metrics['Article_Recall@5'] * 100:.2f}%"
        print(f"{mode:<28} | {rec1:<10} | {rec3:<10} | {rec5:<10} | {rec10:<10} | {art5:<10}")
    print("-" * len(header))

    rg = summary["refusal_gate"]
    print(f"\n2. Kết quả bộ lọc từ chối ({summary['out_of_scope_total']} câu ngoài phạm vi / bẫy):")
    print(f"   - Tỷ lệ từ chối đúng (TRR) : {rg['refusal_precision']} ({rg['true_refusal_rate']}%)")
    print(f"   - Tỷ lệ từ chối nhầm (FRR): {rg['false_refusal_count']} ({rg['false_refusal_rate']}%)")
    print(f"   - Tỷ lệ lọt câu bẫy (FAR)  : {rg['false_acceptance_rate']}%")

    print(f"\n3. Độ chính xác tổng thể ({summary['total_questions']} câu):")
    print(f"   - Tỷ lệ xử lý chuẩn xác: {summary['system_accuracy']}%")
    print("=" * 90)


def main() -> None:
    parser = argparse.ArgumentParser(description="Đánh giá hiệu năng tầng truy hồi RAG.")
    parser.add_argument("--dataset", type=Path, default=config.DATA_DIR / "evaluation" / "dev_set.json", help="Đường dẫn file dev_set.json")
    parser.add_argument("--chunks", type=Path, default=config.CHUNKS_PATH, help="Đường dẫn file chunks.jsonl")
    parser.add_argument("--output", type=Path, default=config.PROJECT_ROOT / "evaluation" / "recall_results.json", help="File lưu kết quả chi tiết")
    args = parser.parse_args()

    print("Đang nạp dữ liệu và tài nguyên phục vụ đánh giá...")
    questions = load_dataset(args.dataset)
    provisions = load_corpus(args.chunks)

    embedder = get_embedder()
    faiss_index = FaissFlatIndex.load(config.FAISS_INDEX_PATH)

    enriched_texts = [
        f"[{p.law_code}] Điều {p.article_no}. {p.title}\n{f'Khoản {p.clause_no}. ' if p.clause_no else ''}{p.text}"
        for p in provisions
    ]
    bm25_index = Bm25Index(enriched_texts, [p.provision_id for p in provisions])

    summary, detailed_results = evaluate_system(questions, provisions, embedder, faiss_index, bm25_index)
    print_summary_table(summary)

    output_data = {
        "summary": summary,
        "results": detailed_results,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n-> Đã lưu kết quả chi tiết vào: {args.output}")


if __name__ == "__main__":
    main()
