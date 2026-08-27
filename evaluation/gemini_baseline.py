"""Chạy thử nghiệm đối chứng No-RAG (hỏi trực tiếp Gemini không kèm tài liệu luật):
- Gửi các câu hỏi trong dev_set.json sang Gemini với cùng prompt quy tắc chuẩn.
- Lưu kết quả ra file baseline_results.json để đối chiếu tỷ lệ ảo giác với RAG.
- Có hỗ trợ lưu tự động từng câu (resume) và cờ --force nếu muốn chạy lại từ đầu.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

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

import config
from generation.llm import generate_no_rag


def _call_with_retry(query: str, max_retries: int = 3) -> str:
    """Gọi Gemini sinh câu trả lời, nếu chạm trần rate limit 429 thì tự động đợi rồi thử lại."""
    for attempt in range(1, max_retries + 1):
        try:
            ans = generate_no_rag(query)
            if ans and not ans.startswith("[Baseline No-RAG] Cần có"):
                return ans
            if ans.startswith("[Baseline No-RAG] Cần có"):
                return ans
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                wait_sec = 20 * attempt
                print(f"\n  [Cảnh báo 429] Đang chạm trần RPM của Gemini. Chờ {wait_sec}s để hồi hạn ngạch (lần {attempt}/{max_retries})...")
                time.sleep(wait_sec)
            else:
                print(f"\n  [Lỗi kết nối] {e}. Thử lại sau 5s...")
                time.sleep(5)
    return "[Lỗi] Không thể lấy phản hồi sau nhiều lần thử do hạn ngạch API."


def run_baseline_no_rag(
    dataset_path: Path | None = None,
    output_path: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 4.0,
    force: bool = False,
) -> None:
    """Chạy lần lượt các câu hỏi và lưu câu trả lời trực tiếp từ Gemini."""
    if dataset_path is None:
        dataset_path = config.DATA_DIR / "evaluation" / "dev_set.json"
    if output_path is None:
        output_path = Path(__file__).resolve().parent / "baseline_results.json"

    if not dataset_path.exists():
        print(f"[Lỗi] Không tìm thấy file bộ câu hỏi tại: {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = data if isinstance(data, list) else data.get("questions", [])
    if limit is not None:
        questions = questions[:limit]

    # Đọc kết quả cũ nếu có để hỗ trợ chạy tiếp câu còn thiếu (khi không bật --force)
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

    success_count = sum(1 for r in results_dict.values() if r.get("status") == "success")
    print(f"Bắt đầu chạy đối chứng No-RAG cho {len(questions)} câu hỏi...")
    if force:
        print("-> Chế độ --force: Bỏ qua kết quả cũ, chạy lại từ đầu 100%.")
    elif results_dict:
        print(f"-> Chế độ Resume: Đã có {len(results_dict)} câu trong lịch sử ({success_count} thành công), sẽ chạy tiếp các câu còn lại hoặc bị lỗi.")

    for i, item in enumerate(questions, 1):
        q_id = item.get("id", str(i))
        q_text = item.get("question", "")
        q_group = item.get("group", "unknown")
        gold_ids = item.get("gold_ids", [])

        # Nếu câu này đã chạy thành công trước đó thì bỏ qua
        if not force and q_id in results_dict and results_dict[q_id].get("status") == "success":
            print(f"[{i}/{len(questions)}] Câu {q_id}: Đã có kết quả thành công từ trước, bỏ qua.")
            continue

        print(f"[{i}/{len(questions)}] Đang gửi câu hỏi {q_id}: {q_text[:60]}...")
        t0 = time.time()
        answer = _call_with_retry(q_text)
        elapsed = time.time() - t0

        if answer.startswith("[Lỗi]"):
            status = "error"
            error_msg = "API Error or Quota Exceeded"
        else:
            status = "success"
            error_msg = ""

        record = {
            "id": q_id,
            "group": q_group,
            "question": q_text,
            "gold_ids": gold_ids,
            "baseline_answer": answer,
            "execution_time_seconds": round(elapsed, 3),
            "status": status
        }
        if error_msg:
            record["error"] = error_msg
            
        results_dict[q_id] = record

        # Lưu ngay xuống file sau mỗi câu để không bị mất dữ liệu nếu đứt mạng
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(list(results_dict.values()), f, ensure_ascii=False, indent=2)

        # Nghỉ giữa các câu để tránh chạm trần 15 RPM của gói Free
        time.sleep(delay_seconds)

    final_success = sum(1 for r in results_dict.values() if r.get("status") == "success")
    print(f"\nHoàn thành đối chứng No-RAG. Thành công: {final_success}/{len(questions)} câu. Đã lưu tại: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy đối chứng Zero-shot No-RAG trên tập câu hỏi kiểm thử.")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng câu hỏi để test thử (ví dụ: --limit 5)")
    parser.add_argument("--delay", type=float, default=4.0, help="Khoảng nghỉ giữa mỗi câu (mặc định 4.0s để không dính trần RPM)")
    parser.add_argument("--force", action="store_true", help="Chạy lại mới hoàn toàn từ đầu, ghi đè kết quả cũ")
    args = parser.parse_args()
    run_baseline_no_rag(limit=args.limit, delay_seconds=args.delay, force=args.force)


if __name__ == "__main__":
    main()
