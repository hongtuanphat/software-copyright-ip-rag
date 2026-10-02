# BƯỚC 5: TÁCH TẬP DỮ LIỆU & THỰC NGHIỆM BASELINES

## 1. Mục tiêu
Tách biệt môi trường tinh chỉnh tham số (Tuning) và môi trường đánh giá cuối cùng (Testing). Thiết lập đủ các cấu hình đường cơ sở (Baseline) để chứng minh ưu thế của hệ thống.

## 2. Vấn đề hiện tại (Theo bug.txt)
- Ngưỡng cosine 0.22 và K=15 được chỉnh trên chính tập 100 câu báo cáo. (Data Leakage nghiêm trọng).
- Chưa có Baseline Long-Context để đối đầu trực tiếp.

## 3. Kế hoạch hành động chi tiết
- **Data Split:**
  - Chia `dev_set.json` thành 2 phần: Tập Dev (dùng để test và set threshold) và Tập Test (Khóa lại, chỉ chạy 1 lần cuối). Đảm bảo không trùng ID.
- **Thực thi Ablation Tests:**
  - Thêm cờ chạy: `Hybrid CÓ nhánh Entity` vs `Hybrid KHÔNG nhánh Entity` (để xem nó đóng góp bao nhiêu cho Nhóm 3).
  - Thêm cờ chạy: Gate ngữ nghĩa + từ khóa vs Gate CHỈ dùng ngữ nghĩa.
- **Thực thi 3 Baselines quan trọng:**
  1. `Dense-only RAG`: Chỉ chạy nhánh FAISS.
  2. `BM25 + Gemini`: Chạy end-to-end nhánh BM25.
  3. `Long-context Baseline`: Đưa thẳng toàn bộ 1375 chunks của cơ sở dữ liệu vào prompt Gemini (Không qua Retrieval) để đối đầu trực tiếp về khả năng tìm kiếm nội tại của LLM.

## 4. Nghiệm thu
- Kiểm tra danh sách câu hỏi trong `dev_set.json` và `test_set.json` không có câu nào trùng lặp nội dung hay ID -> PASS.
- Pipeline hỗ trợ cờ (arguments) trên command line `--pipeline long-context`, `--disable-entity`.
