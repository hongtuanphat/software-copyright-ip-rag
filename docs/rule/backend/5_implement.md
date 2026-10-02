# 5. IMPLEMENTATION (BACKEND)

## Mục đích
Đối chiếu thiết kế và mã nguồn Backend.

## Kiến trúc File
- `ingestion/chunker.py`: Thực hiện chia chunk theo logic Điều/Khoản.
- `ingestion/utils.py`: (Cần bổ sung) Nơi chứa `build_index_text()`.
- `retrieval/embedder.py`: Tích hợp mô hình SentenceTransformer.
- `retrieval/bm25_index.py`: Lưu và tải BM25 index.
- `retrieval/retriever.py`: Cài đặt Hybrid Search và RRF.
- `generation/refusal_gate.py`: Chứa các thuật toán chặn.

## Discrepancies & Issues (Theo bug.txt)
**DISCREPANCY 1:**
- *Intended:* Sử dụng pyvi để tách từ, áp dụng cho cả BM25 và Dense. Max sequence length = 256.
- *Actual:* Code hiện tại đưa text thô vào Embedder; BM25 dùng regex `\w+` để cắt bigram; `config.MAX_SEQ_LENGTH` không được sử dụng.
- *Issue:* Model không hiểu đúng âm tiết tiếng Việt, giảm mạnh chất lượng Dense Search (Dense Recall@1 chỉ 14,29%).
- *Fix Required:* Sửa `embedder.py` và `bm25_index.py` tích hợp `pyvi` vào `build_index_text()`. Chạy lại ablation Dense/BM25/Hybrid.

**DISCREPANCY 2:**
- *Intended:* Hệ thống báo lỗi cứng nếu mô hình nhúng bị lỗi.
- *Actual:* Sử dụng `HashingFallbackEmbedder` im lặng thay thế khi có lỗi.
- *Issue:* Lỗi silent fallback che lấp vấn đề hệ thống, không ghi embedder đã dùng vào file kết quả.
- *Fix Required:* Xóa `HashingFallbackEmbedder`. Bắn `RuntimeError` ngay lập tức. Bổ sung `embedder.model_name`, số chiều, commit hash.

**DISCREPANCY 3:**
- *Intended:* Refusal Gate dựa trên keyword chung và phân loại.
- *Actual:* `OUT_OF_SCOPE_KEYWORDS` chứa cụm copy nguyên văn từ tập test (VD: "mẫu biểu số mấy", "tự bịa ra điều luật"). Gate ngữ nghĩa gần như vô dụng vì 23/30 câu đều bị chặn bởi keyword.
- *Issue:* Data leakage (Rò rỉ dữ liệu đánh giá vào hệ thống huấn luyện/rules). Overfitting tập test.
- *Fix Required:* Dọn sạch keyword rác. Cần thiết kế cơ chế thật (phân loại ý định hoặc gọi LLM có ngữ cảnh) thay cho từ khóa đối với Nhóm 4, 5c. Thêm 30-50 câu held-out để đánh giá thật.
