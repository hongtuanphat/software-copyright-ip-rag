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


def execute_with_retry(func: Callable, max_retries: int = 3, fallback_prefix: str | None = None, *args: Any, **kwargs: Any) -> Any:
    """Thực thi hàm có cơ chế retry tự động khi gặp lỗi 429 hoặc trả về fallback.
    
    Args:
        func: Hàm cần thực thi (vd: pipeline.query, generate, generate_no_rag)
        max_retries: Số lần thử tối đa
        fallback_prefix: Chuỗi prefix nhận diện kết quả là fallback (vd: "[Chế độ Fallback")
    """
    res = None
    for attempt in range(1, max_retries + 1):
        try:
            res = func(*args, **kwargs)
            
            # Check if result is a string or object with fallback prefix
            is_fallback = False
            if fallback_prefix:
                if isinstance(res, str) and res.startswith(fallback_prefix):
                    is_fallback = True
                elif hasattr(res, "answer") and isinstance(res.answer, str) and res.answer.startswith(fallback_prefix):
                    is_fallback = True
                    
            if not is_fallback:
                return res
            
            # Nếu là fallback do rate limit/lỗi, nhưng nếu attempt cuối thì vẫn phải return
            if attempt < max_retries:
                wait_sec = 20 * attempt
                print(f"\n  [Cảnh báo] Trả về fallback (có thể 429). Chờ {wait_sec}s để hồi hạn ngạch (lần {attempt}/{max_retries})...")
                time.sleep(wait_sec)
                
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
                if attempt < max_retries:
                    wait_sec = 20 * attempt
                    print(f"\n  [Cảnh báo 429] Đang chạm trần RPM. Chờ {wait_sec}s để hồi hạn ngạch (lần {attempt}/{max_retries})...")
                    time.sleep(wait_sec)
                    continue
            else:
                if attempt < max_retries:
                    print(f"\n  [Lỗi kết nối] {e}. Thử lại sau 5s...")
                    time.sleep(5)
                    continue
            
            if attempt == max_retries:
                raise Exception(f"Không thể lấy phản hồi sau {max_retries} lần thử do lỗi: {e}")
                
    return res


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

    # Thay vì ghi đè, chúng ta sẽ nối tiếp (do tên file đã có timestamp độc nhất)
    with open(output_path, "a", encoding="utf-8") as out_f:
        for i, item in enumerate(questions, 1):
            q_id = item.get("id", str(i))
            q_text = item.get("question", "")
            q_group = item.get("group", "unknown")
            expected_behavior = item.get("expected_behavior", "answer")
            gold_ids = item.get("gold_ids", [])

            print(f"[{i}/{len(questions)}] Đang xử lý {experiment_name} cho câu {q_id}: {q_text[:60]}...")

            experiment_retries = 0
            max_experiment_retries = 3
            
            while experiment_retries < max_experiment_retries:
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
                            "retrieved_ids": result.get("retrieved_ids", []),
                            "citations": result.get("citations", []),
                            "refused": result.get("refused", False),
                            "latency_ms": round(latency_ms, 2),
                            "status": "success"
                        }
                    }

                    # Ghi ngay xuống file
                    out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out_f.flush()

                    # Tránh Rate limit trước khi chạy câu tiếp theo
                    time.sleep(delay_seconds)
                    
                    # Thành công thì thoát vòng lặp while để đi sang câu mới
                    break
                    
                except Exception as e:
                    experiment_retries += 1
                    if experiment_retries >= max_experiment_retries:
                        print(f"  -> [Lỗi cứng] Đã thử {max_experiment_retries} lần vẫn lỗi: {str(e)}. Ghi nhận lỗi và bỏ qua.")
                        
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
                                "citations": [],
                                "refused": None,
                                "latency_ms": round(latency_ms, 2),
                                "status": "error",
                                "error": str(e),
                            }
                        }
                        out_f.write(json.dumps(error_record, ensure_ascii=False) + "\n")
                        out_f.flush()
                        break
                    print(f"  -> [Lỗi] {str(e)}. Hệ thống sẽ chờ 10s và tự động thử lại (lần {experiment_retries}/{max_experiment_retries})...")
                    time.sleep(10)

    print(f"\nHoàn thành chạy {experiment_name}. Kết quả được lưu tại: {output_path}")
