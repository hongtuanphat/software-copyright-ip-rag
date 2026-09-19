"""evaluation/scripts/run_recall.py

Đo lường độ chính xác của tầng truy hồi (Retrieval) trên tập dev_set.json:
- Tính Recall@1, Recall@3, Recall@5, Recall@10 trên 3 phương pháp:
  1. Dense (FAISS)
  2. Sparse (BM25)
  3. Hybrid (FAISS+BM25+RRF)
- Đánh giá ở cả 2 cấp độ: đúng chính xác Khoản luật (chỉ số chính) và đúng cấp Điều luật (chẩn đoán).
- Tự động in bảng so sánh và lưu kết quả chi tiết từng câu vào recall_results.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Đảm bảo chạy từ thư mục gốc
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.core.runner import setup_encoding
setup_encoding()

import datetime
import numpy as np

import config
from ingestion.chunker import Provision, load_provisions
from retrieval.bm25_index import Bm25Index
from retrieval.embedder import get_embedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import retrieve, retrieve_bm25, retrieve_hybrid
from evaluation.core.metrics import recall_at_k, hierarchical_article_recall_at_k


def load_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    """Đọc bộ câu hỏi kiểm thử từ file json hoặc jsonl."""
    if not dataset_path.exists():
        raise FileNotFoundError(f"Không tìm thấy tập dữ liệu kiểm thử tại: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "questions" in data:
        return data["questions"]
    if isinstance(data, list):
        return data
    raise ValueError("Định dạng file dev_set.json không hợp lệ.")


# Sử dụng shared utility thay vì duplicate logic đọc chunks
load_corpus = load_provisions


def evaluate_system(
    questions: list[dict[str, Any]],
    provisions: list[Provision],
    embedder: Any,
    faiss_index: FaissFlatIndex,
    bm25_index: Bm25Index,
    k_values: list[int] = [1, 3, 5, 10],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Chạy đo lường toàn diện trên 3 chế độ: Dense, BM25, Hybrid."""
    results_by_mode: dict[str, dict[str, list[float]]] = {
        "Dense (FAISS)": {f"recall@{k}": [] for k in k_values} | {f"article_recall@{k}": [] for k in k_values},
        "Sparse (BM25)": {f"recall@{k}": [] for k in k_values} | {f"article_recall@{k}": [] for k in k_values},
        "Hybrid (FAISS+BM25+RRF)": {f"recall@{k}": [] for k in k_values} | {f"article_recall@{k}": [] for k in k_values},
    }

    eval_questions = []
    excluded_questions = []
    for q in questions:
        if q.get("expected_behavior") == "answer":
            eval_questions.append(q)
        else:
            excluded_questions.append(q)
            
    if excluded_questions:
        print(f"[Exclude Logging] Đã loại bỏ {len(excluded_questions)} câu (ngoài phạm vi) khỏi tập tính Recall.")
        excluded_ids = [str(q.get("id")) for q in excluded_questions]
        print(f"[Exclude Logging] Các ID bị loại: {', '.join(excluded_ids)}")
        
    detailed_results: list[dict[str, Any]] = []

    for q in eval_questions:
        q_id = q.get("id", "")
        q_group = q.get("group", "")
        query_text = q.get("question", "")
        gold_ids = q.get("gold_ids") or q.get("ground_truth_provisions") or []

        # 1. Chạy Dense
        dense_hits = retrieve(query_text, provisions, embedder, faiss_index, top_k=max(k_values))
        dense_pids = [h.provision.provision_id for h in dense_hits]

        # 2. Chạy BM25
        bm25_hits = retrieve_bm25(query_text, provisions, bm25_index, top_k=max(k_values))
        bm25_pids = [h.provision.provision_id for h in bm25_hits]

        # 3. Chạy Hybrid
        hybrid_hits = retrieve_hybrid(query_text, provisions, embedder, faiss_index, bm25_index, top_k=max(k_values))
        hybrid_pids = [h.provision.provision_id for h in hybrid_hits]

        # Tính metric 1 lần cho mỗi mode, tái sử dụng cho cả query_record và results_by_mode
        mode_results: dict[str, dict[str, float]] = {}
        for mode_name, pids in [
            ("Dense (FAISS)", dense_pids),
            ("Sparse (BM25)", bm25_pids),
            ("Hybrid (FAISS+BM25+RRF)", hybrid_pids),
        ]:
            mode_metrics: dict[str, float] = {}
            for k in k_values:
                r_k = recall_at_k(gold_ids, pids, k)
                art_r_k = hierarchical_article_recall_at_k(gold_ids, pids, k)
                mode_metrics[f"recall@{k}"] = r_k
                mode_metrics[f"article_recall@{k}"] = art_r_k
                results_by_mode[mode_name][f"recall@{k}"].append(r_k)
                results_by_mode[mode_name][f"article_recall@{k}"].append(art_r_k)
            mode_results[mode_name] = mode_metrics

        query_record: dict[str, Any] = {
            "id": q_id,
            "group": q_group,
            "question": query_text,
            "gold_ids": gold_ids,
            "dense": {"retrieved_ids": dense_pids, **mode_results["Dense (FAISS)"]},
            "bm25": {"retrieved_ids": bm25_pids, **mode_results["Sparse (BM25)"]},
            "hybrid": {"retrieved_ids": hybrid_pids, **mode_results["Hybrid (FAISS+BM25+RRF)"]},
        }
        detailed_results.append(query_record)

    summary: dict[str, Any] = {"total_evaluated_questions": len(eval_questions), "modes": {}}
    for mode_name, metrics in results_by_mode.items():
        summary["modes"][mode_name] = {
            metric_name: round(float(np.mean(vals)), 4) if vals else 0.0
            for metric_name, vals in metrics.items()
        }
    return summary, detailed_results


def print_summary_table(summary: dict[str, Any]) -> None:
    """In bảng so sánh chỉ số trực quan ra màn hình."""
    print("=" * 95)
    print(f"BÁO CÁO ĐO LƯỜNG ĐỘ CHÍNH XÁC TRUY HỒI (RECALL) TRÊN {summary['total_evaluated_questions']} CÂU HỎI")
    print("=" * 95)
    print(f"{'Phương Pháp Truy Hồi':<36} | {'Recall@1':<10} | {'Recall@3':<10} | {'Recall@5':<10} | {'Recall@10':<10} | {'Article@5':<10}")
    print("-" * 95)

    for mode_name, metrics in summary["modes"].items():
        r1 = f"{metrics.get('recall@1', 0.0)*100:.2f}%"
        r3 = f"{metrics.get('recall@3', 0.0)*100:.2f}%"
        r5 = f"{metrics.get('recall@5', 0.0)*100:.2f}%"
        r10 = f"{metrics.get('recall@10', 0.0)*100:.2f}%"
        art5 = f"{metrics.get('article_recall@5', 0.0)*100:.2f}%"
        print(f"{mode_name:<36} | {r1:<10} | {r3:<10} | {r5:<10} | {r10:<10} | {art5:<10}")
    print("=" * 95)

def main() -> None:
    dataset_path = config.DATA_DIR / "evaluation" / "dev_set.json"
    chunks_path = config.CHUNKS_PATH
    faiss_index_path = config.FAISS_INDEX_PATH
    
    output_dir = config.PROJECT_ROOT / "evaluation" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "recall_results.json"

    print("Đang nạp dữ liệu và tài nguyên phục vụ đánh giá Recall...")
    questions = load_dataset(dataset_path)
    provisions = load_corpus(chunks_path)

    embedder = get_embedder()
    faiss_index = FaissFlatIndex.load(faiss_index_path)

    # Khởi tạo chỉ mục BM25 với thông tin bổ sung (metadata) 
    enriched_texts = [
        f"[{p.law_code}] Điều {p.article_no}. {p.title}\n{f'Khoản {p.clause_no}. ' if p.clause_no else ''}{p.text}"
        for p in provisions
    ]
    bm25_index = Bm25Index(enriched_texts, [p.provision_id for p in provisions])

    summary, detailed_results = evaluate_system(questions, provisions, embedder, faiss_index, bm25_index)
    print_summary_table(summary)

    # Lưu đầy đủ kết quả chi tiết từng câu và bảng tổng kết
    output_payload = {
        "summary": summary,
        "results": detailed_results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)
    print(f"-> Đã tự động cập nhật kết quả CHI TIẾT {len(detailed_results)} câu hỏi vào: {output_path}")


if __name__ == "__main__":
    main()
