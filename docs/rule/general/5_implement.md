# 5. IMPLEMENTATION (GENERAL)

## Mục đích
Đối chiếu thiết kế với thực tế source code, bao gồm các khác biệt cần xử lý.

## Cấu trúc Implementation
Hệ thống được tổ chức thành các gói:
* `ingestion/`: Chứa mã nguồn làm sạch, chunking, xây dựng corpus.
* `retrieval/`: Chứa định nghĩa `bm25_index.py`, `embedder.py` và `retriever.py` (RRF).
* `generation/`: Chứa `refusal_gate.py` và bộ gọi LLM.
* `evaluation/`: Scripts benchmark đo lường.
* `webapp/`: UI Streamlit.

## Đối chiếu & Discrepancy
**DISCREPANCY 1:**
- *Intended Design:* Đánh giá hệ thống RAG độc lập và khách quan trên tập dữ liệu tách biệt. Báo cáo dựa trên kết quả cuối cùng.
- *Actual Implementation:* Code hiện tại chưa tự động hóa quy trình đánh giá thành một pipeline nhất quán; script đánh giá nằm rải rác; file kết quả json bị lưu đè lộn xộn.
- *Issue:* Báo cáo (BAOCAO.txt) trích dẫn số liệu không đồng nhất và không thể tái lập (VD: "hơn 17.14%" nhưng thực chất là chênh lệch recall).
- *Resolution:* Cần hợp nhất thành một master script (`run_all.py`) chạy 1 lần, xuất kết quả có version (commit hash).

**DISCREPANCY 2:**
- *Intended Design:* 3 nhánh Hybrid được hợp nhất bằng RRF với `k=15`, trọng số bằng nhau.
- *Actual Implementation:* Một số mô tả dùng tên gọi không nhất quán với RRF ba nhánh.
- *Issue:* Sai lệch kiến trúc giữa tài liệu và code.
- *Resolution:* Sửa code và docs thành "Hybrid RRF (RRF_K=15)".
