"""evaluation/runner.py

Cung cấp hàm để chạy thử nghiệm đánh giá các mô hình RAG, BM25 và Gemini.
"""
from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path
from typing import Callable, Any

import os

def setup_encoding() -> None:
    """Thiết lập encoding UTF-8 cho console để in tiếng Việt không bị lỗi font."""
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    os.environ["PYTHONIOENCODING"] = "utf-8"

# Đổi terminal Windows sang UTF-8 để in tiếng Việt không bị lỗi font
setup_encoding()

import config



_current_retry_count = 0

def execute_with_retry(func: Callable, max_retries: int = 3, *args: Any, **kwargs: Any) -> Any:
    """Thực thi hàm với retry cho lỗi API có thể phục hồi.
    
    Args:
        func: Hàm cần thực thi (vd: pipeline.query, generate, generate_no_rag)
        max_retries: Số lần thử tối đa
    """
    global _current_retry_count
    for attempt in range(1, max_retries + 1):
        _current_retry_count = attempt - 1
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            print(f"\n[Chi tiết lỗi lần {attempt}] {type(e).__name__}: {e}")
            
            if any(k in err_str for k in ["429", "resource_exhausted", "quota"]):
                if attempt < max_retries:
                    wait_sec = 10 * attempt
                    import re
                    match = re.search(r"retrydelay[\'\":\s]+(\d+)s?", err_str, re.IGNORECASE)
                    if match:
                        wait_sec = int(match.group(1)) + 2  # Thêm 2 giây đệm
                    
                    print(f"  -> [Cảnh báo Quota/Rate Limit 429] Đang luân phiên API Key và thử lại sau {wait_sec}s...")
                    time.sleep(wait_sec)
                    continue
            elif any(k in err_str for k in ["500", "503", "504", "unavailable", "deadline", "timeout"]):
                if attempt < max_retries:
                    wait_sec = 20 * attempt
                    print(f"  -> [Cảnh báo Server Overload] Chờ {wait_sec}s để server Google phục hồi...")
                    time.sleep(wait_sec)
                    continue
            else:
                print(f"  -> [Lỗi Client/Hệ thống] Không retry cho loại lỗi này.")
                raise Exception(f"Lỗi cứng từ client: {e}") from e
            
            if attempt == max_retries:
                raise Exception(f"Không thể lấy phản hồi sau {max_retries} lần thử do lỗi: {e}") from e
                
    raise RuntimeError("Không thể hoàn tất lời gọi sau số lần retry cho phép.")


def run_evaluation_experiment(
    experiment_name: str,
    process_func: Callable[[str], dict[str, Any]],
    dataset_path: Path | None = None,
    output_path: Path | None = None,
    limit: int | None = None,
    delay_seconds: float = 4.0,
) -> None:
    """
    Chạy thử nghiệm trên tập dữ liệu và lưu kết quả.

    Args:
        experiment_name: Tên của thử nghiệm (ví dụ: 'RAG', 'BM25', 'Gemini No-RAG').
        process_func: Hàm callback nhận vào `question_text` (str) và trả về một dict 
                      chứa các keys: 'answer', 'retrieved_ids', 'citations', 'refused'.
        dataset_path: Đường dẫn file dataset (dev_set.json).
        output_path: Đường dẫn file ghi kết quả (jsonl).
        limit: Số lượng câu hỏi tối đa muốn chạy.
        delay_seconds: Khoảng thời gian ngủ giữa mỗi câu để tránh rate limit.
    """
    if dataset_path is None:
        dataset_path = config.DATA_DIR / "evaluation" / "dev_set.json"

    if output_path is None:
        time_str = datetime.datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
        output_dir = config.PROJECT_ROOT / "evaluation" / "results" / time_str
        output_dir.mkdir(parents=True, exist_ok=True)
        # Sử dụng tiền tố tên dựa trên experiment_name cho default path
        safe_name = experiment_name.replace(" ", "_").replace("-", "").lower()
        output_path = output_dir / f"{safe_name}.jsonl"

    if not dataset_path.exists():
        print(f"[Lỗi] Không tìm thấy tập dữ liệu tại: {dataset_path}")
        return

    # Đọc câu hỏi
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    questions = data if isinstance(data, list) else data.get("questions", [])
    if limit is not None:
        questions = questions[:limit]

    print(f"Bắt đầu chạy thử nghiệm {experiment_name} cho {len(questions)} câu hỏi...")

    # Đọc các ID đã được xử lý thành công để hỗ trợ chạy tiếp (resume)
    # Các record bị "error" sẽ không được đưa vào set này để chạy lại.
    valid_records = {}
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        record = json.loads(line)
                        q_id = record.get("request", {}).get("id")
                        if q_id:
                            # Luôn lấy bản ghi mới nhất (đề phòng file cũ đã có duplicate)
                            valid_records[q_id] = record
                    except Exception:
                        pass

    # Lọc bỏ các record lỗi 
    valid_records = {k: v for k, v in valid_records.items() if v.get("response", {}).get("status") != "error"}
    processed_ids = set(valid_records.keys())

    if processed_ids:
        print(f"Đã tìm thấy {len(processed_ids)} câu hỏi đã xử lý thành công. Các câu lỗi sẽ được chạy lại.")
        # Ghi đè lại file chỉ với các record hợp lệ
        with open(output_path, "w", encoding="utf-8") as f:
            for rec in valid_records.values():
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Mở file ở chế độ ghi tiếp (a)
    with open(output_path, "a", encoding="utf-8") as out_f:
        for i, item in enumerate(questions, 1):
            q_id = item.get("id", str(i))
            
            # Bỏ qua nếu đã xử lý thành công rồi
            if q_id in processed_ids:
                print(f"[{i}/{len(questions)}] Bỏ qua câu {q_id} (đã xử lý trước đó).")
                continue
                
            q_text = item.get("question", "")
            q_group = item.get("group", "unknown")
            expected_behavior = item.get("expected_behavior", "answer")
            gold_ids = item.get("gold_ids", [])

            print(f"[{i}/{len(questions)}] Đang xử lý {experiment_name} cho câu {q_id}: {q_text[:60]}...")

            start_time = time.perf_counter()
            try:
                # Gọi hàm sinh kết quả cho câu hỏi
                result = process_func(q_text)
                
                latency_ms = (time.perf_counter() - start_time) * 1000.0

                record = {
                    "request": {
                        "id": q_id,
                        "question": q_text,
                        "group": q_group,
                        "expected_behavior": expected_behavior,
                        "gold_ids": gold_ids,
                    },
                    "response": {
                        "answer": result.get("answer"),
                        "raw_answer": result.get("raw_answer", result.get("answer")),
                        "retrieved_ids": [h.get("provision_id") for h in result.get("retrieval_hits", [])],
                        "used_citations": result.get("used_citations", []),
                        "citation_candidates": result.get("retrieval_hits", []),
                        "cited_documents": result.get("cited_documents", []),
                        "refused": result.get("is_refused", False),
                        "refusal_reason": result.get("refusal_reason", ""),
                        "latency_ms": round(latency_ms, 2),
                        "retry_count": _current_retry_count,
                        "status": "success"
                    }
                }

                # Ghi ngay xuống file
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                out_f.flush()

            except Exception as e:
                print(f"  -> [Lỗi] Đã thử hết số lần retry trong hệ thống nhưng vẫn thất bại: {str(e)}. Ghi nhận lỗi và bỏ qua.")
                
                # Ghi error record để evaluation biết câu nào bị miss
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                error_record = {
                    "request": {
                        "id": q_id,
                        "question": q_text,
                        "group": q_group,
                        "expected_behavior": expected_behavior,
                        "gold_ids": gold_ids,
                    },
                    "response": {
                        "answer": None,
                        "retrieved_ids": [],
                        "used_citations": [],
                        "citation_candidates": [],
                        "refused": None,
                        "latency_ms": round(latency_ms, 2),
                        "retry_count": _current_retry_count,
                        "status": "error",
                        "error": str(e),
                    }
                }
                out_f.write(json.dumps(error_record, ensure_ascii=False) + "\n")
                out_f.flush()
            
            finally:
                time.sleep(delay_seconds)

    print(f"\nHoàn thành chạy {experiment_name}. Kết quả được lưu tại: {output_path}")
