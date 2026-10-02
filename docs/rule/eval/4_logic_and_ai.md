# 4. LOGIC + AI (EVALUATION)

## Mục đích
Mô tả các công thức tính toán độ đo (Metrics).

## Thống kê Phân loại (Confusion Matrix)
Dựa trên Nhóm câu hỏi, định nghĩa `in_scope`: Nhóm 1,2,3 là True; Nhóm 4,5 là False.
* `TPR` = Trả lời đúng phạm vi.
* `TN` = Từ chối đúng ngoài phạm vi.
* `FP (FAR)` = Trả lời nhầm ngoài phạm vi (Tỷ lệ chấp nhận nhầm).
* `FN (FRR)` = Từ chối nhầm trong phạm vi (Tỷ lệ từ chối nhầm).
* **Accuracy Formula:**
  `Acc = (Count(in_scope AND correct_clause) + Count(NOT in_scope AND is_refused)) / Total Questions`

## Thống kê Trích dẫn (Citation Metrics)
Cho mảng `C` là danh sách IDs trích xuất từ câu trả lời của LLM; mảng `G` là `gold_ids`.
* **Citation Precision:** `len(C intersection G) / len(C)`
* **Citation Recall:** `len(C intersection G) / len(G)`
* **Citation Exact Match (CEM):** `1.0` nếu `Set(C) == Set(G)` ngược lại `0.0`.
