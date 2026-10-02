# 2. FEATURES (EVALUATION)

## Mục đích
Tính năng của module đánh giá.

## Tính năng
1. **Data Splitting & Held-out Sets:** Tách `dev_set.json` ra làm tập tuning và tạo tập `test_set.json` (chứa các câu hỏi Nhóm 4, Nhóm 5) chưa từng thấy để khóa test set và đảm bảo đánh giá thật.
2. **Master Orchestrator Script (`run_all.py`):** Script duy nhất nhận tham số CLI, gọi tuần tự toàn bộ pipeline (Recall -> Generation -> CEM parsing -> Metric calculation).
3. **Regex Citation Engine (`run_CEM.py`):** Đọc output string của LLM, trích xuất marker `[số]`, đối chiếu với `gold_ids`.
4. **Bootstrapping Statistical Tool:** Tính khoảng tin cậy 95% dựa trên Bootstrap resampling.
5. **Ablation & Baseline Testing Engine:** Hỗ trợ chạy các Baseline: No-RAG, BM25+Gemini, Dense-only RAG, và Long-context (đưa thẳng 1375 chunks vào LLM) để chứng minh tính vượt trội của Hybrid RAG.
