"""Script chạy Gemini baseline trên tập câu hỏi (không RAG)."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Thêm thư mục gốc vào sys.path để chạy trực tiếp script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
import google.generativeai as genai

INSTRUCTION = """Bạn là một trợ lý AI hỗ trợ trả lời các câu hỏi về pháp luật Việt Nam liên quan đến quyền tác giả đối với chương trình máy tính.

Hãy trả lời câu hỏi của người dùng bằng tiếng Việt, rõ ràng và tự nhiên.

Chỉ trả lời dựa trên kiến thức mà bạn có. Không được giả định rằng bạn đã được cung cấp tài liệu pháp luật hoặc context bên ngoài câu hỏi.

Nếu không chắc chắn về thông tin pháp lý, hãy nói rõ mức độ không chắc chắn thay vì tự bịa căn cứ pháp lý.

Không được đề cập đến việc bạn đang thực hiện một thí nghiệm benchmark hoặc baseline."""


def run_gemini(question: str, model_name: str) -> str:
    """Gọi Gemini API với instruction cố định và câu hỏi."""
    model = genai.GenerativeModel(model_name)
    prompt = f"{INSTRUCTION}\n\nCâu hỏi: {question}"
    response = model.generate_content(prompt)
    return response.text


def save_results(results_dict: dict, output_path: Path) -> None:
    """Lưu kết quả ra file JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(list(results_dict.values()), f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy Gemini baseline (No RAG).")
    parser.add_argument("--limit", type=int, help="Giới hạn số lượng câu hỏi để test", default=None)
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Lỗi: Không tìm thấy GEMINI_API_KEY trong environment.")
        sys.exit(1)
        
    genai.configure(api_key=api_key)
    
    input_path = PROJECT_ROOT / "data" / "evaluation" / "questions.json"
    output_path = PROJECT_ROOT / "data" / "evaluation" / "gemini_results.json"
    
    if not input_path.exists():
        print(f"Lỗi: Không tìm thấy dataset tại {input_path}")
        sys.exit(1)
        
    with open(input_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
        
    print(f"Đã nạp {len(questions)} câu hỏi từ {input_path}")
    
    if args.limit:
        questions = questions[:args.limit]
        print(f"Giới hạn chạy: {args.limit} câu")
        
    # Đọc kết quả cũ để phục vụ tính năng Resume
    results_dict = {}
    if output_path.exists():
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                old_results = json.load(f)
                for r in old_results:
                    results_dict[r["id"]] = r
            
            success_count = sum(1 for r in results_dict.values() if r.get("status") == "success")
            print(f"Đã tìm thấy file kết quả cũ ({len(results_dict)} records, {success_count} câu đã thành công).")
        except Exception as e:
            print(f"Lỗi đọc file kết quả cũ, sẽ chạy lại từ đầu: {e}")

    for i, item in enumerate(questions):
        q_id = item["id"]
        
        # Bỏ qua nếu câu hỏi này đã chạy thành công trước đó
        if q_id in results_dict and results_dict[q_id].get("status") == "success":
            print(f"Bỏ qua [{i+1}/{len(questions)}] ID: {q_id} (Đã có kết quả thành công).")
            continue
            
        question = item["question"]
        print(f"Đang xử lý [{i+1}/{len(questions)}] ID: {q_id}...")
        
        try:
            answer = run_gemini(question, config.GEMINI_MODEL_NAME)
            results_dict[q_id] = {
                "id": q_id,
                "answer": answer,
                "model": config.GEMINI_MODEL_NAME,
                "status": "success"
            }
            # Lưu ngay xuống file
            save_results(results_dict, output_path)
            
            # Trễ nhỏ tránh dồn dập request
            time.sleep(1)
            
        except Exception as e:
            error_msg = str(e)
            
            # Phân loại lỗi và tạo chuỗi báo lỗi ngắn gọn
            if "429" in error_msg or "Quota exceeded" in error_msg:
                short_error = "429 Quota Exceeded"
                print(f"  [DỪNG] Bị chặn bởi rate limit (HTTP 429).")
                is_quota_error = True
            else:
                short_error = "API Error"
                print(f"  [LỖI] Gọi API thất bại cho ID {q_id}")
                is_quota_error = False

            # Chỉ lưu ngắn gọn vào file
            results_dict[q_id] = {
                "id": q_id,
                "answer": "",
                "model": config.GEMINI_MODEL_NAME,
                "status": "error",
                "error": short_error
            }
            save_results(results_dict, output_path)
            
            if is_quota_error:
                break # Ngắt vòng lặp nếu là lỗi 429

    print(f"\nTiến trình kết thúc. Đã lưu kết quả tại {output_path}")


if __name__ == "__main__":
    main()
