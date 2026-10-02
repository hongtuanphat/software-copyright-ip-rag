# 3. TECH SOLUTIONS (FRONTEND & DOCS)

## Mục đích
Lý giải công cụ được sử dụng để xây dựng UI và chỉnh sửa Text.

## Giải pháp
* **Streamlit Framework:** Giải pháp tạo Webapp bằng Python nhanh chóng. Lợi thế: Cấu trúc tương thích dễ dàng với hệ thống backend RAG, hỗ trợ markdown và rendering dữ liệu có cấu trúc (JSON, Expander).
* **Regex Engine:** Xử lý chuỗi (String Manipulation) trực tiếp trên output của LLM để tìm các con số nằm giữa ngoặc vuông `\[\d+\]`.
* **Quy trình soát lỗi Báo cáo (Proofreading Pipeline):** Rà soát ngữ nghĩa, kiểm tra chéo (Cross-check) số liệu với output từ file JSON của Evaluation Pipeline để điền số tự động hoặc thủ công chuẩn xác.
