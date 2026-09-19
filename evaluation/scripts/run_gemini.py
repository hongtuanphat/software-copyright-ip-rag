"""evaluation/run_gemini.py

Chạy thử nghiệm đối chứng No-RAG (hỏi trực tiếp Gemini không kèm tài liệu luật).
- Output được lưu vào evaluation/results/gemini_results.jsonl theo đúng schema JSONL.
- Có hỗ trợ lưu tự động từng câu (resume) và đếm số câu thành công.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any



# Đảm bảo chạy từ thư mục gốc
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from generation.llm import generate_no_rag
from evaluation.core.runner import run_evaluation_experiment, execute_with_retry


def _call_with_retry(query: str, max_retries: int = 3) -> str:
    """Gọi Gemini sinh câu trả lời, sử dụng execute_with_retry để xử lý lỗi 429."""
    return execute_with_retry(
        func=generate_no_rag,
        max_retries=max_retries,
        fallback_prefix=None,
        query=query
    )


def run_baseline_no_rag(
    dataset_path: Path | None = None,
    output_path: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 4.0,
) -> None:
    def process_func(q_text: str) -> dict[str, Any]:
        answer = _call_with_retry(q_text)
        return {
            "answer": answer,
            "retrieved_ids": [],
            "citations": [],
            "refused": None,  # Gemini No-RAG baseline không có cơ chế Refusal Gate
        }

    run_evaluation_experiment(
        experiment_name="Gemini No-RAG",
        process_func=process_func,
        dataset_path=dataset_path,
        output_path=output_path,
        limit=limit,
        delay_seconds=delay_seconds,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy đối chứng Zero-shot No-RAG trên tập câu hỏi kiểm thử.")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng câu hỏi để test thử (ví dụ: --limit 5)")
    parser.add_argument("--delay", type=float, default=4.0, help="Khoảng nghỉ giữa mỗi câu (mặc định 4.0s để không dính trần RPM)")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn file output")
    args = parser.parse_args()
    out_path = Path(args.output) if args.output else None
    run_baseline_no_rag(limit=args.limit, delay_seconds=args.delay, output_path=out_path)

if __name__ == "__main__":
    main()
