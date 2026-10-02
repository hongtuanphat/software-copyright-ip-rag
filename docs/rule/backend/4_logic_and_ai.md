# 4. LOGIC + AI (BACKEND)

## Mục đích
Mô tả thuật toán xử lý dữ liệu của Backend.

## Thuật toán truy hồi lai (Hybrid RRF)
Nhận vào truy vấn `Q`.
1. `L_dense = FAISS(Q, top=K)`
2. `L_sparse = BM25(Q, top=K)`
3. `L_entity = RegexBoost(Q, top=K)` (Chỉ kích hoạt nếu `Q` có số Điều/Khoản).
4. Khởi tạo `scores = dict()`
5. Vòng lặp cho mỗi `L` thuộc tập `{L_dense, L_sparse, L_entity}`:
   - Vòng lặp cho mỗi văn bản `d` với hạng `r` trong `L`:
     - `scores[d] = scores[d] + (1 / (15 + r))`
6. Trả về văn bản được sắp xếp theo `scores` giảm dần.

## Logic của Refusal Gate
1. **Rule-based (Keyword):** Duyệt truy vấn `Q` với tập `OUT_OF_SCOPE_KEYWORDS`. Trả về `True` (chặn) nếu khớp.
2. **Semantic Similarity (Cosine Threshold):** Nếu Max Cosine Similarity của `L_dense < 0.22`, hệ thống kết luận truy vấn không liên quan corpus hiện tại -> Chặn.
3. **Data Quality (Distractor Ratio):** Tính số chunk là "distractor" trong Top-K của FAISS. Nếu tỷ lệ `> 0.6`, hệ thống nhận diện truy vấn bị nhiễu do corpus -> Chặn.
