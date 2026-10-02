# 3. TECH SOLUTIONS (GENERAL)

## Mục đích
Biện luận cho sự lựa chọn giải pháp công nghệ của dự án.

## Kiến trúc và Giải pháp kỹ thuật
* **Kiến trúc cốt lõi:** RAG (Retrieval-Augmented Generation) End-to-End.
* **Retrieval Technologies (Hybrid 3 nhánh):**
  - **Dense (FAISS với Sentence-Transformers):** Xử lý ngữ nghĩa ẩn, tìm các từ đồng nghĩa mà người dùng hay dùng (ví dụ: "phần mềm" thay cho "chương trình máy tính").
  - **Sparse (BM25 - rank-bm25):** Tối ưu hóa cho truy vấn chứa thuật ngữ đặc thù hoặc viện dẫn số Điều, số Khoản đích danh.
  - **Entity Regex:** Bắt trực tiếp số hiệu Điều, Khoản để tăng điểm cứng (Boost).
* **Fusion Technology:** **RRF (Reciprocal Rank Fusion)** với hằng số làm mịn `k=15`.
  - *Lý do:* RRF hiệu quả trong việc hợp nhất hai không gian xếp hạng khác biệt mà không cần chuẩn hóa điểm số cosine và BM25.
* **Ngôn ngữ & NLP:** Tiền xử lý tách từ (Word Segmentation) với `VnCoreNLP`.
  - *Lý do:* Khắc phục lỗi tokenizer tự nhiên khi Embedder/BM25 hiểu sai phân mảnh âm tiết tiếng Việt.
* **LLM Engine:** Google Gemini (Gemini-3.5-Flash-Lite).
  - *Lý do:* Năng lực xử lý tiếng Việt trôi chảy, window context đủ rộng, chi phí thấp cho đánh giá hàng loạt.
