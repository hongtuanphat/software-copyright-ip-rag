"""evaluation/run_BM25.py

Chạy thử nghiệm trên 100 câu hỏi (dev_set.json) chỉ sử dụng mô hình BM25 để retrieval.
Output được lưu vào evaluation/results/bm25_results.jsonl
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
from ingestion.chunker import Provision, load_provisions
from retrieval.bm25_index import Bm25Index
from retrieval.retriever import retrieve_bm25
from generation.llm import generate
from generation.prompt_builder import build_prompt
from generation.citation import build_citations
from evaluation.core.runner import run_evaluation_experiment, execute_with_retry


def _generate_with_retry(q_text: str, prompt: str, hits: list, max_retries: int = 3) -> str:
    """Gọi generate, sử dụng execute_with_retry để xử lý fallback/429."""
    return execute_with_retry(
        func=generate,
        max_retries=max_retries,
        fallback_prefix="[Chế độ Fallback",
        query=q_text,
        prompt=prompt,
        hits=hits
    )


def run_bm25_experiment(
    dataset_path: Path | None = None,
    output_path: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 4.0,
) -> None:
    # Tải dữ liệu chunks và khởi tạo BM25
    print("Đang nạp dữ liệu chunks và khởi tạo BM25 index...")
    provisions = load_provisions(config.CHUNKS_PATH)
                
    texts = [p.text for p in provisions]
    pids = [p.provision_id for p in provisions]
    bm25_index = Bm25Index(texts, pids)

    def process_func(q_text: str) -> dict[str, Any]:
        hits = retrieve_bm25(q_text, provisions, bm25_index, top_k=config.TOP_K)
        retrieved_ids = [h.provision.provision_id for h in hits]
        
        prompt = build_prompt(q_text, hits)
        answer = _generate_with_retry(q_text, prompt, hits)
        
        citations = build_citations(hits)
        
        return {
            "answer": answer,
            "retrieved_ids": retrieved_ids,
            "citations": citations,
            "refused": None,  
        }

    run_evaluation_experiment(
        experiment_name="BM25",
        process_func=process_func,
        dataset_path=dataset_path,
        output_path=output_path,
        limit=limit,
        delay_seconds=delay_seconds,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy thử nghiệm BM25 + Gemini trên tập câu hỏi kiểm thử.")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng câu hỏi")
    parser.add_argument("--delay", type=float, default=4.0, help="Khoảng nghỉ giữa mỗi câu")
    parser.add_argument("--output", type=str, default=None, help="Đường dẫn file output")
    args = parser.parse_args()
    out_path = Path(args.output) if args.output else None
    run_bm25_experiment(limit=args.limit, delay_seconds=args.delay, output_path=out_path)

if __name__ == "__main__":
    main()

