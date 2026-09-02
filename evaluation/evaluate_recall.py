"""evaluation/evaluate_recall.py

Đo lường độ chính xác của tầng truy hồi (Retrieval) trên tập dev_set.json:
- Tính Recall@1, Recall@3, Recall@5, Recall@10 trên 4 phương pháp:
  1. Dense (FAISS)
  2. Sparse (BM25)
  3. Hybrid (FAISS+BM25+RRF)
  4. Hybrid + Semantic Reranker (Cross-Encoder)
- Đánh giá ở cả 2 cấp độ: đúng chính xác Khoản luật (chỉ số chính) và đúng cấp Điều luật (chẩn đoán).
- Tự động in bảng so sánh và lưu kết quả chi tiết từng câu vào recall_results.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Nạp thư mục gốc vào sys.path để chạy trực tiếp từ bất kỳ đâu
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Đổi terminal Windows sang UTF-8 để in tiếng Việt không bị lỗi font
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
from retrieval.reranker import get_reranker
from retrieval.retriever import retrieve, retrieve_bm25, retrieve_hybrid, retrieve_with_rerank
from evaluation.metrics import recall_at_k, hierarchical_article_recall_at_k


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


def load_corpus(chunks_path: Path) -> list[Provision]:
    """Nạp danh sách các đoạn luật (Provision) từ file chunks.jsonl."""
    if not chunks_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file chunks tại: {chunks_path}")

    provisions: list[Provision] = []
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                provisions.append(Provision(**json.loads(line)))
    return provisions


def evaluate_system(
    questions: list[dict[str, Any]],
    provisions: list[Provision],
    embedder: Any,
    faiss_index: FaissFlatIndex,
    bm25_index: Bm25Index,
    reranker: Any,
    k_values: list[int] = [1, 3, 5, 10],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Chạy đo lường toàn diện trên 4 chế độ: Dense, BM25, Hybrid và Hybrid + Reranker."""
    results_by_mode: dict[str, dict[str, list[float]]] = {
        "Dense (FAISS)": {f"recall@{k}": [] for k in k_values} | {f"article_recall@{k}": [] for k in k_values},
        "Sparse (BM25)": {f"recall@{k}": [] for k in k_values} | {f"article_recall@{k}": [] for k in k_values},
        "Hybrid (FAISS+BM25+RRF)": {f"recall@{k}": [] for k in k_values} | {f"article_recall@{k}": [] for k in k_values},
        "Hybrid + Reranker (Cross-Encoder)": {f"recall@{k}": [] for k in k_values} | {f"article_recall@{k}": [] for k in k_values},
    }

    # Lọc các câu hỏi có nhãn ground truth (Nhóm 1, 2, 3, 4)
    eval_questions = [q for q in questions if (q.get("gold_ids") or q.get("ground_truth_provisions"))]
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

        # 4. Chạy Hybrid + Reranker
        candidate_k = getattr(config, "RERANK_CANDIDATE_POOL", 20)
        rerank_hits = retrieve_with_rerank(
            query=query_text,
            provisions=provisions,
            embedder=embedder,
            faiss_index=faiss_index,
            bm25_index=bm25_index,
            reranker=reranker,
            candidate_top_k=candidate_k,
            final_top_k=max(k_values),
            min_dense_score=0.0,
        )
        rerank_pids = [h.provision.provision_id for h in rerank_hits]

        query_record: dict[str, Any] = {
            "id": q_id,
            "group": q_group,
            "question": query_text,
            "gold_ids": gold_ids,
            "dense": {
                "retrieved_ids": dense_pids,
                **{f"recall@{k}": recall_at_k(gold_ids, dense_pids, k) for k in k_values},
                **{f"article_recall@{k}": hierarchical_article_recall_at_k(gold_ids, dense_pids, k) for k in k_values},
            },
            "bm25": {
                "retrieved_ids": bm25_pids,
                **{f"recall@{k}": recall_at_k(gold_ids, bm25_pids, k) for k in k_values},
                **{f"article_recall@{k}": hierarchical_article_recall_at_k(gold_ids, bm25_pids, k) for k in k_values},
            },
            "hybrid": {
                "retrieved_ids": hybrid_pids,
                **{f"recall@{k}": recall_at_k(gold_ids, hybrid_pids, k) for k in k_values},
                **{f"article_recall@{k}": hierarchical_article_recall_at_k(gold_ids, hybrid_pids, k) for k in k_values},
            },
            "hybrid_reranker": {
                "retrieved_ids": rerank_pids,
                **{f"recall@{k}": recall_at_k(gold_ids, rerank_pids, k) for k in k_values},
                **{f"article_recall@{k}": hierarchical_article_recall_at_k(gold_ids, rerank_pids, k) for k in k_values},
            },
        }
        detailed_results.append(query_record)

        for mode_name, pids in [
            ("Dense (FAISS)", dense_pids),
            ("Sparse (BM25)", bm25_pids),
            ("Hybrid (FAISS+BM25+RRF)", hybrid_pids),
            ("Hybrid + Reranker (Cross-Encoder)", rerank_pids),
        ]:
            for k in k_values:
                r_k = recall_at_k(gold_ids, pids, k)
                art_r_k = hierarchical_article_recall_at_k(gold_ids, pids, k)
                results_by_mode[mode_name][f"recall@{k}"].append(r_k)
                results_by_mode[mode_name][f"article_recall@{k}"].append(art_r_k)

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
    output_path = Path(__file__).resolve().parent / "recall_results.json"

    print("Đang nạp dữ liệu và tài nguyên phục vụ đánh giá Recall...")
    questions = load_dataset(dataset_path)
    provisions = load_corpus(chunks_path)

    embedder = get_embedder()
    faiss_index = FaissFlatIndex.load(faiss_index_path)

    # Khởi tạo chỉ mục BM25
    bm25_index = Bm25Index([p.text for p in provisions], [p.provision_id for p in provisions])

    # Khởi tạo Semantic Reranker
    reranker = get_reranker()

    summary, detailed_results = evaluate_system(questions, provisions, embedder, faiss_index, bm25_index, reranker)
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
