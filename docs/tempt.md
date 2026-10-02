Mục tiêu không phải là đề xuất sửa ngay, mà phải xác định chính xác:

1. Project hiện tại đã hoàn thành những bước nào trong `fix` / `step.txt`.

2. Từng bước đã hoàn thành đến mức nào: COMPLETE / PARTIAL / MISSING / INCORRECT.

3. Với mỗi bước PARTIAL hoặc INCORRECT:

   * Đã implement được phần nào.
   * Phần nào còn thiếu.
   * Logic hiện tại đang sai hoặc không nhất quán ở đâu.
   * File nào liên quan.
   * Function/class nào liên quan.
   * Dòng code hoặc đoạn code liên quan nếu xác định được.
   * Evidence cụ thể chứng minh kết luận.

4. Kiểm tra xem implementation thực tế có khớp với documentation/rule/specification hay không.

5. Kiểm tra toàn bộ luồng từ:
   Dataset → Retrieval → Hybrid/RRF → Refusal → Generation → Citation → Evaluation → Metrics → Report/Output.

6. Đặc biệt audit kỹ:

   * Dense retrieval
   * BM25
   * Entity retrieval
   * RRF / Adaptive RRF
   * Có reranker thật hay "reranker ảo" không
   * Refusal Gate
   * In-scope / Out-of-scope
   * expected_behavior
   * Recall@K
   * Article/Clause exact match
   * Confusion Matrix
   * CEM
   * Refusal metrics
   * System Accuracy
   * Bootstrap 95% CI
   * Group Breakdown
   * Citation evaluation
   * Data leakage
   * train/dev/test/heldout separation
   * hardcoded/fake data
   * duplicated logic
   * duplicated configuration
   * dead code
   * inconsistent naming
   * inconsistent formulas
   * inconsistent metric definitions
   * code paths that produce different results for the same concept.

7. Chạy test/pytest và các command an toàn cần thiết để VERIFY, nhưng tuyệt đối không thay đổi source code, dataset hoặc output quan trọng.

8. Nếu phát hiện lỗi, KHÔNG FIX. Chỉ ghi nhận lỗi và evidence.

Đặc biệt với phần System Accuracy mà bạn vừa đề xuất:

KHÔNG được mặc định rằng:
`System Accuracy = (article_exact_match_count + true_refusal) / total`

Hãy kiểm tra trước:

* `article_exact_match_count` thực sự đo cái gì.
* Nó có phải "trả lời đúng Khoản" hay không.
* Có bị đếm trùng không.
* `true_refusal` được định nghĩa như thế nào.
* In-scope answer đúng và out-of-scope refusal đúng có đang được đánh giá trên cùng một đơn vị sample không.
* Có các trường hợp answer/refusal khác cần đưa vào công thức không.
* Formula trong code có khớp với formula trong documentation/report không.

Nếu chưa đủ evidence để kết luận System Accuracy nên tính như thế nào thì ghi `UNVERIFIED`, không tự suy luận.

Tương tự với Bootstrap CI:

* Kiểm tra project hiện tại đã có implementation nào chưa.
* Nếu chưa có, chỉ ghi MISSING.
* Không tự thêm implementation.

OUTPUT BẮT BUỘC:

# 1. Current Project Status

Bảng:

| Step | Requirement | Status | Evidence | Missing/Problem |
| ---- | ----------- | ------ | -------- | --------------- |

# 2. Architecture Audit

Mô tả actual flow đang chạy trong project, không mô tả theo documentation nếu implementation thực tế khác.

# 3. Evaluation Audit

Audit riêng toàn bộ Evaluation pipeline:
Dataset → Retrieval → Metrics → Generation → Refusal → CEM → Confusion Matrix → System Accuracy → CI → Group Breakdown.

# 4. Inconsistency / Logic Conflict

Liệt kê tất cả trường hợp:

* cùng một concept nhưng dùng 2 implementation khác nhau
* cùng một metric nhưng công thức khác nhau
* documentation nói A nhưng code làm B
* file A dùng logic khác file B
* output của step trước không khớp input của step sau.

# 5. Bugs / Risks

Phân loại:

* CRITICAL
* HIGH
* MEDIUM
* LOW

Không fix.

# 6. Missing Requirements

Chỉ liệt kê những requirement thực sự chưa có evidence implementation.

# 7. Already Fixed

Liệt kê những vấn đề đã được fix và evidence xác nhận.

# 8. Recommended Fix Order

Chỉ đưa thứ tự ưu tiên sửa, KHÔNG sửa.

# 9. Final Verdict

Kết luận project hiện tại đang ở bước nào trong 8 bước:

* Completed
* Partially completed
* Not completed

Và nêu rõ lý do.

QUAN TRỌNG:

* Không sửa code.
* Không tạo file mới.
* Không thay đổi dataset.
* Không thay đổi config.
* Không "tiện tay" refactor.
* Không coi việc code tồn tại là bằng chứng nó đúng.
* Phải kiểm tra implementation thực tế và execution path.
* Không kết luận dựa trên tên file/function.
* Nếu chưa verify được thì ghi `UNVERIFIED`.
* Nếu phát hiện implementation đúng một phần thì ghi `PARTIAL`, không ghi COMPLETE.
* Không tự đề xuất rằng phải thêm System Accuracy/Bootstrap CI chỉ vì documentation có nói đến; phải xác định requirement đó có thực sự thuộc scope hiện tại và implementation hiện tại đã có hay chưa.
* Đây là AUDIT, không phải CODING TASK.
