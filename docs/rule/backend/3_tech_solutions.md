# 3. TECH SOLUTIONS (BACKEND)

## Mục đích
Lý do chọn thư viện và cấu trúc kỹ thuật Backend.

## Công nghệ sử dụng
* **Sentence Transformers & FAISS:** Dùng để tạo và tra cứu Dense Vector. FAISS phù hợp để quản lý index trên đĩa cứng (disk) hoặc RAM tùy cấu hình.
* **rank-bm25:** Thư viện Python nhẹ, thực thi thuật toán BM25 Okapi cho Sparse Search.
* **pyvi:** Thư viện tách từ tiếng Việt. *Lý do:* Nhanh, nhẹ, dễ tích hợp vào luồng Python hơn VnCoreNLP (yêu cầu Java).
* **Regex Engine (`re`):** Hỗ trợ mạnh mẽ việc trích xuất số Điều, số Khoản từ query và metadata để kích hoạt Entity Boost.

## Trade-offs
* **Word Segmentation:** Việc thêm tách từ tiếng Việt sẽ làm tăng thời gian Ingestion và Query (Latency), tuy nhiên có thể chấp nhận được so với độ tăng Recall (như đã chứng minh trong các thực nghiệm RAG tiếng Việt).
