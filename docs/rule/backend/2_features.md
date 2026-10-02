# 2. FEATURES (BACKEND)

## Mục đích
Các chức năng và API của Backend nhằm đáp ứng Requirement.

## Chức năng
1. **Standardized Index Builder:** Cung cấp hàm `build_index_text()` nhận một đối tượng `Provision` và xuất ra chuỗi đã chuẩn hóa (VD: `[Luật] Điều X. Tiêu đề Khoản Y. Nội dung`).
2. **Vietnamese Segmentation Pipeline:** Pipeline bọc ngoài (Wrapper) cho `pyvi` hoặc `VnCoreNLP`, áp dụng tại thời điểm index tài liệu và thời điểm xử lý truy vấn (Query).
3. **Strict Embedder Initialization:** Module khởi tạo mô hình FAISS/SentenceTransformer với tính năng kiểm tra tính toàn vẹn và cấu hình bắt buộc (`max_seq_length = 256`).
4. **Refusal Gate Logic Module:** Module thực hiện chặn truy vấn qua 3 bước (từ khóa, ngưỡng tìm kiếm, tỷ lệ nhiễu).
