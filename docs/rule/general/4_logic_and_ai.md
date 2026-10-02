# 4. LOGIC + AI (GENERAL)

## Mục đích
Mô tả chi tiết luồng dữ liệu, thuật toán và suy luận của toàn hệ thống.

## Processing Flow
1. **Query Preprocessing:** 
   - Chuỗi truy vấn `Q` -> Chuyển chữ thường, xóa khoảng trắng thừa -> Tách từ tiếng Việt -> `Q_processed`.
2. **Retrieval Pipeline:**
   - Đưa `Q_processed` vào 3 nhánh đồng thời:
     - Nhánh 1 (BM25): Tính Term Frequency & IDF -> `Rank_sparse`.
     - Nhánh 2 (Dense): `Embed(Q_processed)` -> FAISS Vector Search -> `Rank_dense`.
     - Nhánh 3 (Entity): Regex bắt số hiệu, khớp regex -> `Rank_entity`.
   - **Fusion (RRF Logic):** 
     - `Score(d) = sum(1 / (15 + rank_i(d)))`.
   - Trọng số 3 nhánh là ngang bằng (1:1:1), với hằng số RRF `k=15`.
3. **Refusal Gate Logic (3 Tầng):**
   - *Tầng 1 (Keyword tĩnh):* Kiểm tra các từ khóa nằm ngoài phạm vi SHTT.
   - *Tầng 2 (Cosine Threshold):* Lấy Max Cosine của Dense Retrieval. Nếu `< 0.22`, chặn.
   - *Tầng 3 (Distractor Ratio):* Tính tỷ lệ chunk nhiễu trong Top-K. Nếu `> 0.6`, chặn.
4. **Generation & Citation Parsing:**
   - RAG Prompt cấu trúc: `Context + Query`. Yêu cầu LLM sinh câu trả lời kèm `[số]`.
   - Output LLM -> Regex bóc tách `[số]` -> Map với ID trong CSDL.
