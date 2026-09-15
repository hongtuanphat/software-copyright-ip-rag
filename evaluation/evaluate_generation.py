"""
Đánh giá và so sánh chất lượng câu trả lời giữa mô hình RAG và Baseline (No-RAG)
trên tập câu hỏi kiểm thử.

Các chỉ số đánh giá:
- Citation Match: Tỷ lệ trích dẫn khớp với điều, khoản luật chuẩn.
- Article Mention Rate: Tỷ lệ câu trả lời nhắc đúng số Điều luật liên quan.
- Refusal Accuracy: Tỷ lệ nhận biết và từ chối các câu hỏi bẫy hoặc ngoài phạm vi.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Nạp thư mục gốc vào sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Thiết lập UTF-8 cho Windows console
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"

import numpy as np
import config


def _extract_article_no(provision_id: str) -> str:
    """Lấy số Điều từ mã điều khoản (ví dụ: 67-VBHN-VPQH_Art22_Kh1 -> 22)."""
    m = re.search(r"Art([0-9]+[a-z]?)", provision_id, re.IGNORECASE)
    return m.group(1).lower() if m else ""


def check_citation_match(gold_ids: list[str], citations: list[dict[str, Any]]) -> dict[str, bool]:
    """Kiểm tra trích dẫn của câu trả lời có khớp với điều, khoản chuẩn hay không."""
    if not gold_ids:
        return {"has_clause_hit": True, "has_article_hit": True}

    cited_ids = {c.get("provision_id", "") for c in citations if c.get("provision_id")}
    has_clause_hit = any(gid in cited_ids for gid in gold_ids)

    gold_articles = {_extract_article_no(gid) for gid in gold_ids if _extract_article_no(gid)}
    cited_articles = {_extract_article_no(cid) for cid in cited_ids if _extract_article_no(cid)}
    has_article_hit = bool(gold_articles.intersection(cited_articles))

    return {
        "has_clause_hit": has_clause_hit,
        "has_article_hit": has_article_hit,
    }


def check_article_mention(gold_ids: list[str], answer_text: str) -> bool:
    """Kiểm tra trong nội dung câu trả lời có nhắc đến số Điều đúng hay không."""
    if not gold_ids or not answer_text:
        return False
    gold_articles = {_extract_article_no(gid) for gid in gold_ids if _extract_article_no(gid)}
    text_lower = answer_text.lower()
    return any(f"điều {art}" in text_lower for art in gold_articles)


def is_response_refused(answer_text: str, is_refused_flag: bool = False) -> bool:
    """Kiểm tra câu trả lời có mang tính chất từ chối hay không."""
    if is_refused_flag:
        return True
    text_lower = answer_text.lower()
    refusal_signals = [
        "ngoài phạm vi",
        "không thể trả lời",
        "không thuộc phạm vi",
        "chưa có quy định",
        "chưa bao gồm",
        "không có thông tin",
        "tôi không thể",
        "từ chối",
    ]
    return any(sig in text_lower for sig in refusal_signals)


def evaluate_all_generation(
    dev_set_path: Path | None = None,
    rag_results_path: Path | None = None,
    baseline_results_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """So sánh kết quả sinh câu trả lời giữa RAG và Baseline trên toàn bộ tập kiểm thử."""
    if dev_set_path is None:
        dev_set_path = config.DATA_DIR / "evaluation" / "dev_set.json"
    if rag_results_path is None:
        rag_results_path = Path(__file__).resolve().parent / "rag_results.json"
    if baseline_results_path is None:
        baseline_results_path = Path(__file__).resolve().parent / "baseline_results.json"
    if output_path is None:
        output_path = Path(__file__).resolve().parent / "generation_eval_results.json"

    with open(dev_set_path, "r", encoding="utf-8") as f:
        dev_set = json.load(f)
    if isinstance(dev_set, dict) and "questions" in dev_set:
        dev_set = dev_set["questions"]

    rag_data: dict[str, dict[str, Any]] = {}
    if rag_results_path.exists():
        with open(rag_results_path, "r", encoding="utf-8") as f:
            for item in json.load(f):
                rag_data[item["id"]] = item

    baseline_data: dict[str, dict[str, Any]] = {}
    if baseline_results_path.exists():
        with open(baseline_results_path, "r", encoding="utf-8") as f:
            for item in json.load(f):
                baseline_data[item["id"]] = item

    print(f"Đang phân tích đối chứng trên {len(dev_set)} câu hỏi...")

    detailed_eval: list[dict[str, Any]] = []

    rag_clause_hit_list: list[float] = []
    rag_article_hit_list: list[float] = []
    rag_article_mention_list: list[float] = []
    base_article_mention_list: list[float] = []

    rag_refusal_list: list[float] = []
    base_refusal_list: list[float] = []

    in_scope_count = 0
    out_of_scope_count = 0

    for q in dev_set:
        q_id = q["id"]
        q_text = q["question"]
        gold_ids = q.get("gold_ids", [])
        expected_behavior = q.get("expected_behavior", "answer")

        rag_record = rag_data.get(q_id, {})
        rag_ans = rag_record.get("rag_answer", rag_record.get("answer", ""))
        rag_citations = rag_record.get("citations", [])
        rag_refused = rag_record.get("is_refused", False)

        base_record = baseline_data.get(q_id, {})
        base_ans = base_record.get("baseline_answer", base_record.get("answer", ""))

        cit_match = check_citation_match(gold_ids, rag_citations)
        rag_mentions_art = check_article_mention(gold_ids, rag_ans)
        base_mentions_art = check_article_mention(gold_ids, base_ans)

        if expected_behavior == "answer":
            in_scope_count += 1
            rag_clause_hit_list.append(1.0 if cit_match["has_clause_hit"] else 0.0)
            rag_article_hit_list.append(1.0 if cit_match["has_article_hit"] else 0.0)
            rag_article_mention_list.append(1.0 if rag_mentions_art else 0.0)
            base_article_mention_list.append(1.0 if base_mentions_art else 0.0)
        else:
            out_of_scope_count += 1
            rag_refusal_list.append(1.0 if rag_refused else 0.0)
            base_refused_ok = is_response_refused(base_ans, False)
            base_refusal_list.append(1.0 if base_refused_ok else 0.0)

        detailed_eval.append({
            "id": q_id,
            "group": q.get("group", ""),
            "question": q_text,
            "expected_behavior": expected_behavior,
            "gold_ids": gold_ids,
            "rag": {
                "answer": rag_ans,
                "is_refused": rag_refused,
                "citation_match": cit_match,
                "mentions_gold_article": rag_mentions_art,
            },
            "no_rag_baseline": {
                "answer": base_ans,
                "mentions_gold_article": base_mentions_art,
            },
        })

    summary = {
        "total_evaluated": len(dev_set),
        "in_scope_total": in_scope_count,
        "out_of_scope_total": out_of_scope_count,
        "rag": {
            "citation_clause_match": round(float(np.mean(rag_clause_hit_list)), 4) if rag_clause_hit_list else 0.0,
            "citation_article_match": round(float(np.mean(rag_article_hit_list)), 4) if rag_article_hit_list else 0.0,
            "article_mention_rate": round(float(np.mean(rag_article_mention_list)), 4) if rag_article_mention_list else 0.0,
            "refusal_accuracy": round(float(np.mean(rag_refusal_list)), 4) if rag_refusal_list else 1.0,
        },
        "no_rag_baseline": {
            "citation_clause_match": 0.0,
            "article_mention_rate": round(float(np.mean(base_article_mention_list)), 4) if base_article_mention_list else 0.0,
            "refusal_accuracy": round(float(np.mean(base_refusal_list)), 4) if base_refusal_list else 0.0,
        },
    }

    output_data = {
        "summary": summary,
        "results": detailed_eval,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print_summary_table(summary)
    print(f"-> Đã lưu kết quả vào: {output_path}")

    return summary


def print_summary_table(summary: dict[str, Any]) -> None:
    """In bảng so sánh kết quả RAG và Baseline."""
    print("\n" + "=" * 88)
    print("          BẢNG SO SÁNH CHẤT LƯỢNG TRẢ LỜI: RAG VS BASELINE")
    print("=" * 88)
    header = f"{'Chỉ số':<46} | {'RAG Pipeline':<18} | {'No-RAG Baseline':<18}"
    print(header)
    print("-" * len(header))
    rag_m = summary["rag"]
    base_m = summary["no_rag_baseline"]

    c_clause = f"{rag_m['citation_clause_match'] * 100:.2f}%"
    c_art = f"{rag_m['citation_article_match'] * 100:.2f}%"
    m_art = f"{rag_m['article_mention_rate'] * 100:.2f}%"
    r_acc = f"{rag_m['refusal_accuracy'] * 100:.2f}%"

    b_clause = f"{base_m['citation_clause_match'] * 100:.2f}%"
    b_art_m = f"{base_m['article_mention_rate'] * 100:.2f}%"
    b_ref = f"{base_m['refusal_accuracy'] * 100:.2f}%"

    print(f"{'Trích dẫn đúng cấp Khoản (Exact Clause Match)':<46} | {c_clause:<18} | {b_clause:<18}")
    print(f"{'Trích dẫn đúng cấp Điều (Article Match)':<46} | {c_art:<18} | {'0.00%':<18}")
    print(f"{'Nhắc đúng số Điều trong nội dung câu trả lời':<46} | {m_art:<18} | {b_art_m:<18}")
    print(f"{'Khả năng từ chối câu hỏi bẫy / ngoài phạm vi':<46} | {r_acc:<18} | {b_ref:<18}")
    print("=" * 88)


def main() -> None:
    parser = argparse.ArgumentParser(description="Đánh giá chất lượng sinh câu trả lời RAG vs Baseline.")
    parser.add_argument("--dev-set", type=Path, default=None, help="Đường dẫn file dev_set.json")
    parser.add_argument("--rag-results", type=Path, default=None, help="Đường dẫn file rag_results.json")
    parser.add_argument("--baseline-results", type=Path, default=None, help="Đường dẫn file baseline_results.json")
    parser.add_argument("--output", type=Path, default=None, help="Đường dẫn file lưu kết quả")
    args = parser.parse_args()

    evaluate_all_generation(
        dev_set_path=args.dev_set,
        rag_results_path=args.rag_results,
        baseline_results_path=args.baseline_results,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
