"""evaluation/run_RAG.py

Chạy thử nghiệm trên 100 câu hỏi (dev_set.json) sử dụng toàn bộ RAGPipeline.
Output được lưu vào evaluation/results/rag_results.jsonl
Có hỗ trợ resume cho các câu đã thành công.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Đảm bảo chạy từ thư mục gốc
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
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
        fallback_prefix="[Chế độ Fallback",
        question=q_text,
        top_k=config.TOP_K
    )


def run_rag_experiment(
    dataset_path: Path | None = None,
    output_path: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 4.0,
) -> None:
    print("Đang khởi tạo RAGPipeline...")
    # Sử dụng pipeline mặc định của dự án
    pipeline = get_pipeline()

    def process_func(q_text: str) -> dict[str, Any]:
        # Gọi end-to-end pipeline với cơ chế retry
        res = _query_with_retry(pipeline, q_text)
        
        # Trích xuất dữ liệu trả về theo đúng output schema yêu cầu
        retrieved_ids = [h.get("provision_id") for h in res.retrieval_hits]
        
        return {
            "answer": res.answer,
            "retrieved_ids": retrieved_ids,
            "citations": res.citations,
            "refused": res.is_refused,
        }

    run_evaluation_experiment(
        experiment_name="RAG",
        process_func=process_func,
        dataset_path=dataset_path,
        output_path=output_path,
        limit=limit,
        delay_seconds=delay_seconds,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy thử nghiệm System RAG trên tập câu hỏi kiểm thử.")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng câu hỏi")
    parser.add_argument("--delay", type=float, default=4.0, help="Khoảng nghỉ giữa mỗi câu")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn file output")
    args = parser.parse_args()
    out_path = Path(args.output) if args.output else None
    run_rag_experiment(limit=args.limit, delay_seconds=args.delay, output_path=out_path)

if __name__ == "__main__":
    main()
