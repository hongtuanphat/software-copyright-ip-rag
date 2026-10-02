# 1. USER'S REQUIREMENT (BACKEND)

## Mục đích
Mô tả các yêu cầu kỹ thuật và chức năng sâu của phân hệ Backend (Corpus, Retrieval, Generation).

## Yêu cầu chi tiết
* **Đồng nhất dữ liệu Ingestion:** Text đầu vào phải qua một chuẩn định dạng duy nhất trước khi được đưa vào FAISS và BM25. Tránh tình trạng nhánh Dense encode một chuỗi mở rộng, còn nhánh Sparse dùng text trần.
* **Xử lý đặc thù Tiếng Việt:** Phải tích hợp công cụ phân tách âm tiết (word segmentation) chuyên dụng cho tiếng Việt để tránh hiện tượng mất dấu, sai nghĩa, đặc biệt hữu ích cho BM25.
* **Kiểm soát tính ổn định Mô hình (Strict Error Handling):** Quá trình tải mô hình nhúng (Embedder) phải báo lỗi rõ ràng nếu thất bại. Tuyệt đối cấm hệ thống tự động rơi vào cơ chế dự phòng (silent fallback) bằng chuỗi băm (Hashing) làm sai lệch toàn bộ chất lượng Semantic Search.
* **Cổng từ chối minh bạch (Refusal Gate v2):** Phân loại và chặn các câu hỏi cố tình đi chệch khỏi trọng tâm Bản quyền phần mềm. Không được sử dụng thủ thuật học thuộc tập test (data leakage) để chặn.
