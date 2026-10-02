# 5. IMPLEMENTATION (EVALUATION)

## Mục đích
Đối chiếu thiết kế đánh giá với mã nguồn hiện tại.

## Cấu trúc File
- `evaluation/scripts/run_all.py`: Orchestrator (gộp chạy một lần).
- `evaluation/scripts/metrics/run_CEM.py`: Parser Citation.
- `evaluation/scripts/metrics/run_recall.py`: Đánh giá Retriever riêng lẻ.
- `evaluation/scripts/pipelines/run_RAG.py`: Đánh giá hệ thống (RAG, Gemini, BM25+LLM)
- `evaluation/scripts/metrics/run_refusal_metrics.py`: Đánh giá các tham số TP, FP, TN, FN và TRR, FAR, FRR của 3 hệ thống end-to-end. 
- `evaluation/metrics.py`: Chứa định nghĩa công thức toán học.

## Discrepancies & Issues (Theo bug.txt)
**DISCREPANCY 1:**
- *Intended:* Đánh giá Citation (Trích dẫn) phải dựa vào những gì LLM sinh ra.
- *Actual:* Code `build_citations()` trong pipeline chỉ tính dựa trên top-5 chunk của Retriever, hoàn toàn bỏ qua văn bản LLM sinh ra.
- *Issue:* Con số "Clause match 54.29%" trong báo cáo hoàn toàn là số liệu giả (thực chất nó là Retrieval Recall).
- *Fix Required:* Thay thế cơ chế tính. Phải truyền output text của LLM vào `run_CEM.py` để parse bằng regex các chuỗi `[số]`. Ánh xạ về `TÀI LIỆU [i]` và `provision_id`.

**DISCREPANCY 2:**
- *Intended:* Đánh giá phải được điều phối trung tâm và ghi metadata rõ ràng.
- *Actual:* Các file json như `recall_results.json` và `generation_eval_results.json` chứa số liệu mâu thuẫn (VD: TRR 24/30 vs 23/30). File kết quả bị ghi đè không kiểm soát và commit nhầm vào git. Repo dùng chung 1 tập dev_set cho việc tune và báo cáo.
- *Issue:* Vi phạm tính tái lập (Reproducibility). Baseline thiếu thực tế (Chưa có baseline BM25+Gemini và Dense-only RAG, Long-context 1375 chunks).
- *Fix Required:* Viết `run_all.py` gộp quá trình chạy (1 lệnh `main.py --force`). Tách rõ dev_set và test_set. Thêm 3 Baseline. Ghi metadata (commit hash, tên embedder) vào folder `results/{commit_hash}/`. Sửa file `.gitignore`. Phân rã kết quả theo nhóm 1,2,3,4,5a-d vào bảng báo cáo riêng.
