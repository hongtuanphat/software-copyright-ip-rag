# BƯỚC 2: VÁ LỖI CODE NỀN TẢNG (FOUNDATION CODE)

## 1. Mục tiêu
Sửa các lỗi logic thấp (low-level logic) liên quan đến indexing, embedding và config trước khi tiến hành bất kỳ bài đánh giá nào.

## 2. Vấn đề hiện tại (Theo bug.txt)
- `build_index_text`: Branch Dense và Sparse dùng 2 nguồn text đầu vào khác nhau (text làm giàu vs text trần).
- Embedder có thể bị lỗi âm thầm (silent fail) và tự lùi về `HashingFallbackEmbedder`, làm sai lệch toàn bộ chất lượng RAG mà dev không biết.
- Không có tách từ tiếng Việt (`pyvi` hoặc `VnCoreNLP`) cho Dense và BM25, khiến tokenizer cắt sai âm tiết.
- Model sequence length chưa được áp dụng đúng. Cấu hình thừa `REFUSAL_THRESHOLD`.

## 3. Kế hoạch hành động chi tiết
- **Tạo hàm `build_index_text()`:**
  - Viết trong `ingestion/utils.py`. Hàm nhận một object `Provision` và trả về `[Tên Luật] Điều X. Tiêu đề Khoản Y. Nội dung`.
  - Áp dụng hàm này cho cả luồng FAISS và BM25 (sửa ở `main.py`, `pipeline.py`, `run_recall.py`). Dựng lại toàn bộ Index.
- **Xử lý tiếng Việt (Vietnamese Word Segmentation):**
  - Import `pyvi.ViTokenizer.tokenize` và áp dụng trực tiếp cho text trước khi gọi Encode/Index.
- **Quản lý lỗi Embedder:**
  - Sửa hàm `get_embedder()`. Nếu không thể load model thật, `raise RuntimeError` để chương trình dừng ngay lập tức. Xóa `HashingFallbackEmbedder`.
  - Gắn `model.max_seq_length = config.MAX_SEQ_LENGTH`.
- **Dọn dẹp code & Config:**
  - Xóa biến `REFUSAL_THRESHOLD` không dùng trong `config.py`.
  - Sửa docstring của hàm `retrieve_hybrid` để dùng ngưỡng 0.22 theo config. Xử lý lỗi `METADATA_FILE` (chưa push hoặc trỏ sai đường dẫn).

## 4. Nghiệm thu
- Sửa tên model trong config thành một tên fake (vd: "fake_model"). Chạy pipeline. Nếu chương trình văng lỗi (Crash) thay vì im lặng chạy tiếp -> PASS.
- Mở text trước khi vào BM25, in ra terminal phải thấy các từ gạch dưới dạng `chương_trình máy_tính` -> PASS.
