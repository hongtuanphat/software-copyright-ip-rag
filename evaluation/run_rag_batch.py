"""evaluation/run_rag_batch.py

Chạy toàn bộ 100 câu hỏi trong dev_set.json qua hệ thống RAG Pipeline chính thức:
- Gọi hàm answer_rag() từ pipeline.py (có tích hợp Hybrid RRF và Refusal Gate).
- Thu thập câu trả lời RAG, danh sách trích dẫn (citations), cảnh báo và thời gian thực thi.
- Hỗ trợ lưu tự động từng câu (resume), cờ --force và pacing delay tránh rate limit.
- Xuất kết quả ra file evaluation/rag_results.json để phục vụ đánh giá thực nghiệm.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Nạp thư mục gốc vào sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
os.environ["PYTHONIOENCODING"] = "utf-8"

import config
from pipeline import answer_rag


def _call_rag_with_retry(question: str, top_k: int = config.TOP_K, max_retries: int = 3) -> dict[str, Any]:
    """Gọi pipeline RAG, tự động chờ hồi hạn ngạch nếu gặp 429."""
    for attempt in range(1, max_retries + 1):
        try:
            res = answer_rag(question=question, top_k=top_k)
            return res
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                wait_sec = 20 * attempt
                print(f"\n  [Cảnh báo 429] Đang chạm trần RPM. Chờ {wait_sec}s để hồi hạn ngạch (lần {attempt}/{max_retries})...")
                time.sleep(wait_sec)
            else:
                print(f"\n  [Lỗi Pipeline] {e}. Thử lại sau 5s...")
                time.sleep(5)
    return {
        "question": question,
        "answer": "[Lỗi] Không thể sinh phản hồi sau nhiều lần thử.",
        "citations": [],
        "active_alerts": [],
        "is_refused": True,
        "execution_time_seconds": 0.0,
        "error": "Pipeline Failure",
    }


def run_rag_batch(
    dataset_path: Path | None = None,
    output_path: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 4.0,
    force: bool = False,
) -> None:
    """Chạy lần lượt 100 câu hỏi qua RAG Pipeline và lưu kết quả chi tiết."""
    if dataset_path is None:
        dataset_path = config.DATA_DIR / "evaluation" / "dev_set.json"
    if output_path is None:
        output_path = Path(__file__).resolve().parent / "rag_results.json"

    if not dataset_path.exists():
        print(f"[Lỗi] Không tìm thấy file bộ câu hỏi tại: {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = data if isinstance(data, list) else data.get("questions", [])
    if limit is not None:
        questions = questions[:limit]

    # Đọc kết quả cũ nếu có để hỗ trợ resume
    results_dict: dict[str, dict] = {}
    if not force and output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, list):
                    for item in saved:
                        results_dict[item["id"]] = item
        except Exception:
            results_dict = {}

    success_count = sum(1 for r in results_dict.values() if not r.get("answer", "").startswith("[Lỗi]"))
    print(f"Bắt đầu chạy RAG Pipeline cho {len(questions)} câu hỏi...")
    if force:
        print("-> Chế độ --force: Bỏ qua kết quả cũ, chạy lại từ đầu 100%.")
    elif results_dict:
        print(f"-> Chế độ Resume: Đã có {len(results_dict)} câu trong lịch sử ({success_count} thành công), sẽ chạy tiếp các câu còn lại.")

    for i, item in enumerate(questions, 1):
        q_id = item.get("id", str(i))
        q_text = item.get("question", "")
        q_group = item.get("group", "unknown")
        gold_ids = item.get("gold_ids", [])
        expected_behavior = item.get("expected_behavior", "answer")

        # Bỏ qua nếu đã có kết quả thành công
        if not force and q_id in results_dict and not results_dict[q_id].get("answer", "").startswith("[Lỗi]"):
            print(f"[{i}/{len(questions)}] Câu {q_id}: Đã có kết quả RAG từ trước, bỏ qua.")
            continue

        print(f"[{i}/{len(questions)}] Đang xử lý câu hỏi {q_id}: {q_text[:60]}...")
        t0 = time.time()
        res = _call_rag_with_retry(q_text)
        elapsed = time.time() - t0

        record = {
            "id": q_id,
            "group": q_group,
            "question": q_text,
            "gold_ids": gold_ids,
            "expected_behavior": expected_behavior,
            "rag_answer": res.get("answer", ""),
            "is_refused": res.get("is_refused", False),
            "citations": res.get("citations", []),
            "retrieval_hits": res.get("retrieval_hits", []),
            "execution_time_seconds": round(elapsed, 3),
            "active_alerts": res.get("active_alerts", []),
        }
        results_dict[q_id] = record

        # Lưu ngay xuống file sau mỗi câu
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(list(results_dict.values()), f, ensure_ascii=False, indent=2)

        # Nghỉ giữa các câu tránh trần RPM
        time.sleep(delay_seconds)

    final_success = sum(1 for r in results_dict.values() if not r.get("rag_answer", "").startswith("[Lỗi]"))
    print(f"\nHoàn thành RAG Pipeline. Thành công: {final_success}/{len(questions)} câu. Đã lưu tại: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy batch RAG Pipeline trên tập câu hỏi kiểm thử.")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng câu hỏi để test thử")
    parser.add_argument("--delay", type=float, default=4.0, help="Khoảng nghỉ giữa mỗi câu")
    parser.add_argument("--force", action="store_true", help="Chạy lại từ đầu 100%")
    args = parser.parse_args()
    run_rag_batch(limit=args.limit, delay_seconds=args.delay, force=args.force)


if __name__ == "__main__":
    main()
