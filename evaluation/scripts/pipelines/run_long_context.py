"""End-to-end long-context Gemini baseline using the full legal corpus."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from evaluation.core.runner import execute_with_retry, run_evaluation_experiment
from generation.llm import _call_gemini, get_api_key
from ingestion.chunker import load_provisions
from ingestion.utils import build_index_text
from generation.prompt_builder import SYSTEM_INSTRUCTION
from generation.citation_resolver import resolve_citations


def run_long_context_experiment(
    dataset_path: Path | None = None,
    output_path: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 4.0,
) -> None:
    provisions = load_provisions(config.CHUNKS_PATH)
    context = "\n\n".join(
        f"TÀI LIỆU [{index}]:\n{build_index_text(provision)}"
        for index, provision in enumerate(provisions, 1)
    )

    def process_func(question: str) -> dict[str, Any]:
        api_key = get_api_key()
        if not api_key:
            raise RuntimeError("Thiếu GEMINI_API_KEY cho long-context baseline.")
        prompt = (
            f"{SYSTEM_INSTRUCTION}\n\n"
            f"--- TOÀN BỘ CORPUS ({len(provisions)} chunks) ---\n{context}\n\n"
            f"--- CÂU HỎI ---\n{question}"
        )
        import json
        answer_text = execute_with_retry(_call_gemini, prompt=prompt, api_key=api_key, timeout_ms=120000)
        raw_answer_text = answer_text
        try:
            llm_response = json.loads(answer_text)
            answer_content = llm_response.get("answer", "")
            decision_str = str(llm_response.get("decision", "")).strip().upper()
            reason_str = str(llm_response.get("reason", "")).strip()
            raw_used_citations = llm_response.get("used_citations", [])
        except json.JSONDecodeError:
            import logging
            logging.warning(f"Lỗi JSONDecodeError trong long-context: {answer_text}")
            answer_content = answer_text
            decision_str = ""
            reason_str = ""
            raw_used_citations = []
            
        # Tạo danh sách tài liệu ngữ cảnh từ toàn bộ corpus (phục vụ mô hình long-context)
        context_documents = [
            {
                "provision_id": p.provision_id,
                "article_no": p.article_no,
                "clause_no": p.clause_no,
                "title": p.title,
                "score": 1.0,
                "is_distractor": p.is_distractor,
            }
            for p in provisions
        ]
            
        answer_content, cited_documents, used_citations = resolve_citations(answer_content, raw_used_citations, context_documents)
            
        return {
            "answer": answer_content if decision_str != "REFUSE" else "Xin lỗi, câu hỏi nằm ngoài phạm vi.", 
            "raw_answer": raw_answer_text,
            "retrieved_ids": [], 
            "used_citations": used_citations,
            "cited_documents": cited_documents,
            "citation_candidates": [],
            "is_refused": decision_str == "REFUSE",
            "refusal_reason": reason_str,
        }

    run_evaluation_experiment(
        experiment_name="Long-context",
        process_func=process_func,
        dataset_path=dataset_path,
        output_path=output_path,
        limit=limit,
        delay_seconds=delay_seconds,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=4.0)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dataset", type=Path, default=None)
    args = parser.parse_args()
    run_long_context_experiment(
        limit=args.limit,
        delay_seconds=args.delay,
        output_path=args.output,
        dataset_path=args.dataset,
    )
