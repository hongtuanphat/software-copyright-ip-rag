"""evaluation/scripts/pipelines/run_RAG.py

Chạy thử nghiệm đánh giá RAGPipeline (chỉ dành cho Hybrid RAG).
Output được lưu vào evaluation/results/...
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Đảm bảo chạy từ thư mục gốc
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from pipeline import get_pipeline
from evaluation.core.runner import run_evaluation_experiment, execute_with_retry

def _query_with_retry(pipeline, q_text: str, max_retries: int = 3):
    """Gọi pipeline.query, sử dụng execute_with_retry để xử lý fallback/429."""
    return execute_with_retry(
        func=pipeline.query,
        max_retries=max_retries,
        question=q_text,
        top_k=config.TOP_K
    )

def run_hybrid_experiment(
    dataset_path: Path | None = None,
    output_path: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 4.0,
    disable_entity: bool = False,
    semantic_only_gate: bool = False,
) -> None:
    print("Đang khởi tạo RAGPipeline (Hybrid)...")

    pipeline = get_pipeline(
        mode="hybrid",
        enable_entity=not disable_entity,
        use_keywords=not semantic_only_gate,
    )

    def process_func(q_text: str) -> dict[str, Any]:
        res = _query_with_retry(pipeline, q_text)
        retrieved_ids = [h.get("provision_id") for h in res.retrieval_hits]
        return {
            "answer": res.answer,
            "raw_answer": res.raw_answer,
            "retrieved_ids": retrieved_ids,
            "retrieval_hits": res.retrieval_hits,
            "cited_documents": res.cited_documents,
            "is_refused": res.is_refused,
            "refusal_reason": res.refusal_reason,
        }

    experiment_name = "Hybrid"

    run_evaluation_experiment(
        experiment_name=experiment_name,
        process_func=process_func,
        dataset_path=dataset_path,
        output_path=output_path,
        limit=limit,
        delay_seconds=delay_seconds,
    )

def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy thử nghiệm System RAG (Hybrid) trên tập câu hỏi kiểm thử.")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng câu hỏi")
    parser.add_argument("--delay", type=float, default=4.0, help="Khoảng nghỉ giữa mỗi câu")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn file output")
    parser.add_argument("--dataset", type=Path, default=None, help="Dataset tuning/test cần chạy.")
    parser.add_argument("--disable-entity", action="store_true", help="Tắt nhánh Entity trong Hybrid RRF.")
    parser.add_argument(
        "--semantic-only-gate",
        action="store_true",
        help="Tắt keyword layer để chạy ablation semantic-only.",
    )
    args = parser.parse_args()
    
    out_path = Path(args.output) if args.output else None
    run_hybrid_experiment(
        limit=args.limit,
        delay_seconds=args.delay,
        output_path=out_path,
        dataset_path=args.dataset,
        disable_entity=args.disable_entity,
        semantic_only_gate=args.semantic_only_gate,
    )

if __name__ == "__main__":
    main()
