# 3. TECH SOLUTIONS (EVALUATION)

## Mục đích
Lý giải công cụ công nghệ cho Evaluation.

## Giải pháp
* **Thống kê toán học (`scipy.stats.bootstrap`):** Sử dụng lấy mẫu lặp (resampling) để tính 95% CI. Phù hợp cho tập dữ liệu có quy mô nhỏ (N=100 câu hỏi, đặc biệt Nhóm 4 chỉ có 12 câu).
* **CLI Arguments (`argparse`):** Hỗ trợ chạy linh hoạt bằng command line (vd: `--pipeline no-rag`, `--use-long-context`).
* **Regex Engine (`re`):** Giải pháp hiệu quả nhất để thực hiện bóc tách trích dẫn (Parsing Citation) thay vì dùng LLM-as-a-judge (tránh chi phí và ảo giác).
