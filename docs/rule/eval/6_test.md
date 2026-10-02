# 6. TEST (EVALUATION)

## Mục đích
Kiểm thử các script đánh giá.

## Các Test Case Cụ thể
1. **Unit Test Regex Parser (`run_CEM.py`):**
   - Input: `"Tham khảo theo quy định tại [1], khoản 2 Điều 4 [3]."`
   - Expected Output: `[1, 3]`. Đảm bảo regex hoạt động hoàn hảo.
2. **Data Leakage Overlap Check:**
   - Viết script quét qua toàn bộ ID câu hỏi trong `dev_set.json` và `test_set.json`.
   - Expected: Tập hợp ID giao nhau (Intersection) phải rỗng (Đảm bảo độ độc lập hoàn toàn của tập Test).
3. **Pipeline Orchestrator Log Test:**
   - Chạy `python run_all.py`.
   - Expected: Trong folder `evaluation/results/`, tự động sinh ra một folder có tên là SHA hash của git commit hiện tại (hoặc Timestamp). Folder chứa file json có key `model_name` và `embedder`. File này phải bị `.gitignore` bỏ qua.
4. **Baseline Execution Test:**
   - Chạy `--pipeline no-rag` và `--use-long-context`.
   - Expected: No-RAG phải có Clause Match là 0%. Long-context phải load đủ 1375 chunks vào prompt.
