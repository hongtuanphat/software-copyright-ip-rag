"""evaluation/run_gemini.py

Chạy thử nghiệm đối chứng No-RAG (hỏi trực tiếp Gemini không kèm tài liệu luật).
- Output được lưu vào evaluation/results/gemini_results.jsonl theo đúng schema JSONL.
- Có hỗ trợ lưu tự động từng câu (resume) và đếm số câu thành công.
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
    raise Exception("Không thể lấy phản hồi sau nhiều lần thử do hạn ngạch API hoặc lỗi kết nối.")

def load_processed_ids(output_path: Path) -> set[str]:
    """Đọc file jsonl và trả về danh sách các id đã xử lý thành công."""
    processed = set()
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        if record.get("status") == "success":
                            processed.add(record["id"])
                    except json.JSONDecodeError:
                        pass
    return processed

def run_baseline_no_rag(
    dataset_path: Path | None = None,
    output_path: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 4.0,
    force: bool = False,
) -> None:
    if dataset_path is None:
        dataset_path = config.DATA_DIR / "evaluation" / "dev_set.json"
        
    if output_path is None:
        output_dir = Path(__file__).resolve().parent / "results"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "gemini_results.jsonl"

    if not dataset_path.exists():
        print(f"[Lỗi] Không tìm thấy file bộ câu hỏi tại: {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = data if isinstance(data, list) else data.get("questions", [])
    if limit is not None:
        questions = questions[:limit]

    processed_ids = set()
    if not force:
        processed_ids = load_processed_ids(output_path)

    # Nếu dùng force, xóa file cũ nếu có
    if force and output_path.exists():
        output_path.unlink()

    print(f"Bắt đầu chạy đối chứng No-RAG cho {len(questions)} câu hỏi...")
    if force:
        print("-> Chế độ --force: Bỏ qua kết quả cũ, chạy lại từ đầu 100%.")
    elif processed_ids:
        print(f"-> Chế độ Resume: Bỏ qua {len(processed_ids)} câu đã thành công.")

    with open(output_path, "a", encoding="utf-8") as out_f:
        for i, item in enumerate(questions, 1):
            q_id = item.get("id", str(i))
            q_text = item.get("question", "")
            q_group = item.get("group", "unknown")
            expected_behavior = item.get("expected_behavior", "answer")
            gold_ids = item.get("gold_ids", [])

            if not force and q_id in processed_ids:
                print(f"[{i}/{len(questions)}] Câu {q_id}: Đã có kết quả thành công từ trước, bỏ qua.")
                continue

            print(f"[{i}/{len(questions)}] Đang gửi câu hỏi {q_id}: {q_text[:60]}...")
            
            start_time = time.perf_counter()
            try:
                answer = _call_with_retry(q_text)
                latency_ms = (time.perf_counter() - start_time) * 1000.0

                record = {
                    "id": q_id,
                    "question": q_text,
                    "group": q_group,
                    "expected_behavior": expected_behavior,
                    "gold_ids": gold_ids,
                    "answer": answer,
                    "retrieved_ids": [],
                    "citations": [],
                    "refused": False,
                    "latency_ms": round(latency_ms, 2),
                    "status": "success"
                }
            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                print(f"  -> [Lỗi] {str(e)}")
                record = {
                    "id": q_id,
                    "question": q_text,
                    "group": q_group,
                    "expected_behavior": expected_behavior,
                    "gold_ids": gold_ids,
                    "answer": None,
                    "retrieved_ids": [],
                    "citations": [],
                    "refused": False,
                    "latency_ms": round(latency_ms, 2),
                    "status": "error",
                    "error": str(e)
                }

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()

            # Nghỉ giữa các câu để tránh chạm trần 15 RPM của gói Free
            time.sleep(delay_seconds)

    print(f"\nHoàn thành đối chứng No-RAG. Kết quả được lưu tại: {output_path}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy đối chứng Zero-shot No-RAG trên tập câu hỏi kiểm thử.")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng câu hỏi để test thử (ví dụ: --limit 5)")
    parser.add_argument("--delay", type=float, default=4.0, help="Khoảng nghỉ giữa mỗi câu (mặc định 4.0s để không dính trần RPM)")
    parser.add_argument("--force", action="store_true", help="Chạy lại mới hoàn toàn từ đầu, ghi đè kết quả cũ")
    args = parser.parse_args()
    run_baseline_no_rag(limit=args.limit, delay_seconds=args.delay, force=args.force)

if __name__ == "__main__":
    main()
