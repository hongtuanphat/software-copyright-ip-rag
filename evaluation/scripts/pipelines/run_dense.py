"""evaluation/scripts/pipelines/run_dense.py

Chạy thử nghiệm đánh giá sử dụng mô hình FAISS (Dense-only) để retrieval.
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
    """Gọi pipeline.query với retry dùng chung cho evaluation."""
    return execute_with_retry(
        func=pipeline.query,
        max_retries=max_retries,
        question=q_text,
        top_k=config.TOP_K,
    )

def run_dense_experiment(
    dataset_path: Path | None = None,
    output_path: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 4.0,
) -> None:
    print("Đang khởi tạo RAGPipeline (Dense-only)...")
    pipeline = get_pipeline(mode="dense")

    def process_func(q_text: str) -> dict[str, Any]:
        response = _query_with_retry(pipeline, q_text)
        return {
            "answer": response.answer,
            "raw_answer": response.raw_answer,
            "retrieval_hits": response.retrieval_hits,
            "used_citations": response.used_citations,
            "cited_documents": response.cited_documents,
            "is_refused": response.is_refused,
            "refusal_reason": response.refusal_reason,
        }

    run_evaluation_experiment(
        experiment_name="Dense-only",
        process_func=process_func,
        dataset_path=dataset_path,
        output_path=output_path,
        limit=limit,
        delay_seconds=delay_seconds,
    )

def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy thử nghiệm Dense + Gemini.")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng câu hỏi")
    parser.add_argument("--delay", type=float, default=4.0, help="Khoảng nghỉ giữa mỗi câu")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn file output")
    parser.add_argument("--dataset", type=Path, default=None, help="Dataset tuning/test cần chạy.")
    args = parser.parse_args()
    
    out_path = Path(args.output) if args.output else None
    run_dense_experiment(
        limit=args.limit,
        delay_seconds=args.delay,
        output_path=out_path,
        dataset_path=args.dataset,
    )

if __name__ == "__main__":
    main()
