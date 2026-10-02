# 6. TEST (GENERAL)

## Mục đích
Mô tả quy trình kiểm thử và đánh giá hệ thống.

## Chiến lược & Test Data
* **Tập dữ liệu kiểm thử (Benchmark Test Set):** 100 câu hỏi gold.
  - Nhóm 1 (25 câu): Trong phạm vi, trực tiếp.
  - Nhóm 2 (25 câu): Trong phạm vi, tình huống thực tế. (Yêu cầu kiểm tra xử lý ngoại lệ theo thỏa thuận).
  - Nhóm 3 (20 câu): Tra cứu điều khoản.
  - Nhóm 4 (12 câu): Cùng chủ đề nhưng khác văn bản (cần Soft Refusal).
  - Nhóm 5 (18 câu): Khác đối tượng SHTT, sai domain, reasoned refusal, prompt injection (cần Hard Refusal).

## Đánh giá định lượng (Metrics)
1. **Retrieval Metrics:** Recall@K cấp Khoản, Recall@K cấp Điều.
2. **Refusal Metrics (Confusion Matrix):** TRR (True Refusal Rate), FAR (False Acceptance), FRR (False Refusal), SRQR (Soft Refusal Quality Rate).
3. **Citation Metrics:** Citation Exact Match, Precision, Recall.
4. **Generation Metrics (Rubric):** Legal Correctness, Citation Accuracy, Faithfulness & Relevance, Scope Handling (Thang 1-4 điểm).

## Baseline so sánh
Để chứng minh hiệu quả, hệ thống phải chạy so sánh với 3 cấu hình Baseline:
1. Gemini Baseline (No-RAG).
2. BM25 Baseline (Sparse + Gemini).
3. Dense-only RAG.
4. Long-context Baseline (Đưa 1375 chunks trực tiếp vào prompt LLM).
