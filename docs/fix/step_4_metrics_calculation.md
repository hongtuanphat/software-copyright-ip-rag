# BƯỚC 4: SỬA CÁCH TÍNH CÁC CHỈ SỐ THEN CHỐT

## 1. Mục tiêu
Xây dựng logic tính toán các chỉ số độ chính xác (Accuracy) và Citation chuẩn xác theo định nghĩa khoa học.

## 2. Vấn đề hiện tại (Theo bug.txt)
- "Accuracy 63%" chưa được định nghĩa hoặc định nghĩa sai.
- Con số "Clause Match 54.29%" là số ảo. Hàm `build_citations()` thực chất lấy top-5 chunks của Retriever để làm citation, KHÔNG hề phân tích xem LLM có thực sự sử dụng các chunks đó trong câu trả lời hay không. 

## 3. Kế hoạch hành động chi tiết
- **Định nghĩa lại Accuracy System:**
  - Sửa lại code trong `metrics.py` theo công thức: 
    `Accuracy = (Count(in_scope AND correct_clause) + Count(NOT in_scope AND is_refused)) / Total_Queries`.
- **Viết Parser Trích dẫn (Citation Exact Match):**
  - Bỏ cơ chế dùng Retriever Top-K. 
  - Truyền `output_text` do LLM sinh ra vào `run_CEM.py`. Dùng thư viện Regex (`re`) để tìm tất cả các chuỗi có định dạng `[số]`.
  - Từ số thứ tự `[i]`, ánh xạ ngược lại metadata để lấy ra `provision_id`.
  - Thu được tập `LLM_ids`. So sánh tập này với `Gold_ids` để tính:
    - `Citation Precision`
    - `Citation Recall`
    - `Citation Exact Match` (Chỉ tính 1 nếu Set(LLM_ids) == Set(Gold_ids)).

## 4. Nghiệm thu
- Fake một output LLM: "Theo quy định tại [1] và [3]". Chạy parser phải trả về đúng mảng chứa ID của tài liệu 1 và 3.
- Số liệu Citation Accuracy phải phản ánh độc lập so với Retrieval Recall.
