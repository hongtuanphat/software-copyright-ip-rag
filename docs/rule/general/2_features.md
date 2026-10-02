# 2. FEATURES (GENERAL)

## Mục đích
Liệt kê và mô tả các chức năng cốt lõi của hệ thống để giải quyết User Requirement.

## Các chức năng (Features)
1. **Chia nhỏ văn bản thông minh (Contextual Chunking):**
   * **Purpose:** Duy trì ngữ cảnh đầy đủ cho LLM.
   * **Main behavior:** Thay vì cắt theo độ dài ký tự cứng nhắc, hệ thống cắt theo cấu trúc Điều -> Khoản, tự động nối tiền tố (Tên luật - Điều - Khoản) vào mỗi chunk.

2. **Truy hồi thông tin đa nhánh (Hybrid Retrieval):**
   * **Purpose:** Tối đa hóa khả năng định vị chính xác văn bản pháp luật.
   * **Main behavior:** Kết hợp Dense Retrieval (nắm bắt ngữ nghĩa) và Sparse Retrieval (bắt từ khóa chính xác), sau đó hợp nhất bằng thuật toán.

3. **Cổng từ chối đa tầng (Refusal Gate):**
   * **Purpose:** Bảo vệ hệ thống khỏi các truy vấn nằm ngoài phạm vi hoặc cố tình thao túng (prompt injection).
   * **Main behavior:** Đánh giá độ phù hợp của truy vấn trước khi gọi sinh văn bản. Cung cấp cả Từ chối cứng (Hard Refusal) và Từ chối mềm (Soft Refusal).

4. **Trích xuất căn cứ pháp lý thực tế (Citation Extraction):**
   * **Purpose:** Minh bạch hóa câu trả lời.
   * **Main behavior:** Đánh dấu mốc trích dẫn trong văn bản sinh ra, ánh xạ ngược về bộ dữ liệu gốc để người dùng đọc nguyên văn.
