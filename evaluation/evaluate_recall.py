"""evaluation/evaluate_recall.py

Script đánh giá định lượng độ chính xác của Tầng Truy hồi (Retrieval) trên tập dev_set.json:
- Chạy từng câu hỏi kiểm thử qua các pipeline tìm kiếm và tính các chỉ số Recall@1, Recall@3, Recall@5, Recall@10.
- So sánh đối chứng hiệu quả giữa 3 phương pháp:
    1. Single Dense Retrieval (FAISS với mô hình vietnamese-bi-encoder)
    2. Single Sparse Retrieval (BM25Okapi)
    3. Hybrid Search (Kết hợp Dense + BM25 qua thuật toán Reciprocal Rank Fusion - RRF)
- Đánh giá ở cả 2 cấp độ: Cấp Khoản (Exact Clause) và Cấp Điều (Hierarchical Article).

Mỗi câu hỏi có thể có nhiều gold_ids; do đó, Recall@K được tính theo công thức giao tập hợp:
    Recall@K = |Gold ∩ TopK| / |Gold|
(tính đúng theo tỷ lệ các điều luật tìm được trên tổng số điều luật cần tìm, không phải chỉ có 1 hit là 1.0).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Đảm bảo in tiếng Việt chuẩn trên Windows terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"

import numpy as np

import config
from ingestion.chunker import Provision
from retrieval.bm25_index import Bm25Index
from retrieval.embedder import get_embedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import retrieve, retrieve_bm25, retrieve_hybrid


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
    raise ValueError(f"Định dạng dữ liệu không hợp lệ tại {dataset_path}")


def load_corpus(chunks_path: Path) -> list[Provision]:
    """Đọc toàn bộ các đoạn luật (Provision) từ file chunks.jsonl."""
    if not chunks_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file chunks tại: {chunks_path}")

    provisions: list[Provision] = []
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                provisions.append(Provision(**json.loads(line)))
    return provisions


def _extract_article_no(provision_id: str) -> str:
    """Bóc tách số hiệu Điều từ mã định danh provision_id."""
    m = re.search(r"Art(\d+[a-z]?)", provision_id)
    return m.group(1) if m else provision_id


def calculate_recall_at_k(gold_ids: list[str], retrieved_ids: list[str], k: int) -> float:
    """Tính Recall@K ở cấp Khoản (Exact Clause Match)."""
    if not gold_ids:
        return 0.0
    top_k_retrieved = set(retrieved_ids[:k])
    matched = sum(1 for gid in gold_ids if gid in top_k_retrieved)
    return matched / len(gold_ids)


def calculate_hierarchical_recall_at_k(gold_ids: list[str], retrieved_ids: list[str], k: int) -> float:
    """Tính Recall@K ở cấp Điều (Hierarchical Article Match)."""
    if not gold_ids:
        return 0.0
    gold_articles = set(_extract_article_no(gid) for gid in gold_ids)
    retrieved_articles = set(_extract_article_no(rid) for rid in retrieved_ids[:k])
    matched = sum(1 for art in gold_articles if art in retrieved_articles)
    return matched / len(gold_articles)


def evaluate_system(
    questions: list[dict[str, Any]],
    provisions: list[Provision],
    embedder: Any,
    faiss_index: FaissFlatIndex,
    bm25_index: Bm25Index,
    k_values: list[int] = [1, 3, 5, 10],
) -> dict[str, Any]:
    """Chạy đo lường toàn diện trên 3 chế độ: Dense, BM25 và Hybrid."""
    results_by_mode: dict[str, dict[str, list[float]]] = {
        "Dense (FAISS)": {f"recall@{k}": [] for k in k_values} | {f"article_recall@{k}": [] for k in k_values},
        "Sparse (BM25)": {f"recall@{k}": [] for k in k_values} | {f"article_recall@{k}": [] for k in k_values},
        "Hybrid (FAISS+BM25+RRF)": {f"recall@{k}": [] for k in k_values} | {f"article_recall@{k}": [] for k in k_values},
    }

    # Lọc các câu hỏi có nhãn ground truth (Nhóm 1, 2, 3, 4)
    eval_questions = [q for q in questions if (q.get("gold_ids") or q.get("ground_truth_provisions"))]

    for q in eval_questions:
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

        for mode_name, pids in [
            ("Dense (FAISS)", dense_pids),
            ("Sparse (BM25)", bm25_pids),
            ("Hybrid (FAISS+BM25+RRF)", hybrid_pids),
        ]:
            for k in k_values:
                r_k = calculate_recall_at_k(gold_ids, pids, k)
                art_r_k = calculate_hierarchical_recall_at_k(gold_ids, pids, k)
                results_by_mode[mode_name][f"recall@{k}"].append(r_k)
                results_by_mode[mode_name][f"article_recall@{k}"].append(art_r_k)

    summary: dict[str, Any] = {"total_evaluated_questions": len(eval_questions), "modes": {}}
    for mode_name, metrics in results_by_mode.items():
        summary["modes"][mode_name] = {
            metric_name: round(float(np.mean(vals)), 4) if vals else 0.0
            for metric_name, vals in metrics.items()
        }
    return summary


def print_summary_table(summary: dict[str, Any]) -> None:
    """In bảng so sánh chỉ số trực quan ra màn hình."""
    print("=" * 85)
    print(f"BÁO CÁO ĐO LƯỜNG ĐỘ CHÍNH XÁC TRUY HỒI (RECALL) TRÊN {summary['total_evaluated_questions']} CÂU HỎI")
    print("=" * 85)
    print(f"{'Phương Pháp Truy Hồi':<26} | {'Recall@1':<10} | {'Recall@3':<10} | {'Recall@5':<10} | {'Recall@10':<10} | {'Article@5':<10}")
    print("-" * 85)

    for mode_name, metrics in summary["modes"].items():
        r1 = f"{metrics.get('recall@1', 0.0)*100:.2f}%"
        r3 = f"{metrics.get('recall@3', 0.0)*100:.2f}%"
        r5 = f"{metrics.get('recall@5', 0.0)*100:.2f}%"
        r10 = f"{metrics.get('recall@10', 0.0)*100:.2f}%"
        art5 = f"{metrics.get('article_recall@5', 0.0)*100:.2f}%"
        print(f"{mode_name:<26} | {r1:<10} | {r3:<10} | {r5:<10} | {r10:<10} | {art5:<10}")
    print("=" * 85)


def main() -> None:
    dataset_path = config.DATA_DIR / "evaluation" / "dev_set.json"
    chunks_path = config.CHUNKS_PATH
    faiss_index_path = config.FAISS_INDEX_PATH

    print("Đang nạp dữ liệu và tài nguyên phục vụ đánh giá Recall...")
    questions = load_dataset(dataset_path)
    provisions = load_corpus(chunks_path)

    embedder = get_embedder()
    faiss_index = FaissFlatIndex.load(faiss_index_path)

    # Khởi tạo chỉ mục BM25
    bm25_index = Bm25Index([p.text for p in provisions], [p.provision_id for p in provisions])

    summary = evaluate_system(questions, provisions, embedder, faiss_index, bm25_index)
    print_summary_table(summary)


if __name__ == "__main__":
    main()
