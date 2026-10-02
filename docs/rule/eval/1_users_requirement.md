# 1. USER'S REQUIREMENT (EVALUATION)

## Mục đích
Mô tả yêu cầu đối với hệ thống Đánh giá (Evaluation & Metrics) chất lượng dự án.

## Yêu cầu chi tiết
* **Đo lường Khách quan và Khoa học:** Phải xây dựng cơ chế tự động đánh giá mô hình trên tập dữ liệu chuẩn (Benchmark), tính toán độ chính xác theo đúng các khái niệm toán học và xuất báo cáo tin cậy bằng khoảng tin cậy 95% (95% CI - Bootstrapping).
* **Minh bạch hóa Trích dẫn (Citation True Value):** Không được đánh tráo khái niệm. Việc Retriever lấy ra được tài liệu đúng không đồng nghĩa với việc LLM đã dùng tài liệu đó. Phải phân định rõ ràng Retrieval Recall và Citation Exact Match.
* **Tách biệt Dữ liệu (No Data Leakage):** Tuyệt đối không dùng chung một tập dữ liệu vừa để tinh chỉnh (tune) các ngưỡng (threshold 0.22, k=15) vừa để báo cáo kết quả cuối cùng.
* **Quản lý Phiên bản (Version Control):** Mỗi lần chạy thí nghiệm phải tạo ra báo cáo đi kèm metadata (commit hash, tên model, ngày giờ) để lưu vết lịch sử độ chính xác, không dùng chung số liệu của các lần chạy cũ.
