Prompt 3 — Xác minh error records và denominator trước khi sửa metric

Cái này nên tách riêng vì nó ảnh hưởng độ tin cậy của tất cả metric, không chỉ citation.

Đặc biệt audit của bạn có #6/#13 tự mâu thuẫn, nên phải bắt AI đếm dữ liệu thật trước.

Tiếp tục audit project `software-copyright-ip-rag`.

Mục tiêu duy nhất:

> Xác minh bằng evaluation results thực tế xem `status="error"` có đang bị đưa vào denominator của Recall@K và các retrieval metrics hay không, mức ảnh hưởng thực tế là bao nhiêu, và có cần sửa code hay không.

KHÔNG SỬA CODE trong bước này.

Audit trước có các nhận định #5, #6, #13 nhưng một số nhận định tự mâu thuẫn. Không được mặc định tin chúng.

### 1. Trace code

Kiểm tra:

* `runner.py`
* `analysis.py`
* `group_retrieval()`
* `analyze_records()`
* `calculate_metrics()`
* `run_all.py`
* `run_recall.py`

Xác định chính xác:

* record lỗi được tạo thế nào;
* `status` có giá trị gì;
* `retrieved_ids` của error record là gì;
* retrieval metric lấy records nào;
* denominator được tính như thế nào;
* refusal record có `retrieved_ids` hay không;
* error record có bị loại hay không.

### 2. Kiểm tra evaluation results thực tế

Đọc các result JSON/JSONL hiện có.

Không chỉ kiểm tra code.

Thống kê theo từng system:

* total records;
* status=success;
* status=error;
* error rate;
* error records có retrieved_ids hay không;
* refusal records;
* in-scope records;
* out-of-scope records.

### 3. Recalculate Recall độc lập

Từ raw evaluation records, tự tính lại Recall@K theo hai cách:

A. Current implementation.

B. Exclude `status="error"`.

So sánh:

| System | Metric | Current | Exclude errors | Delta |
| ------ | ------ | ------: | -------------: | ----: |

Làm cho ít nhất:

* Recall@1
* Recall@5
* Recall@10
* Recall@20 nếu có.

### 4. Kiểm tra refusal

Đặc biệt xác minh nhận định:

> "refusal làm recall bằng 0"

Không được chấp nhận nhận định này nếu chưa xem record.

Với các query in-scope:

* nếu `refused=True` nhưng `retrieved_ids` vẫn có dữ liệu → retrieval recall có bị tính hay không?
* nếu `retrieved_ids=[]` → tại sao?
* refusal xảy ra trước hay sau retrieval?

Phân biệt:

`retrieval failure`
vs
`refusal decision`
vs
`generation error`.

### 5. Kiểm tra long_context riêng

Nếu long_context có nhiều error records:

* thống kê số lượng;
* tính error rate;
* xác định có được dùng để so sánh với các system khác không.

Không được đưa long_context vào cùng bảng comparison mà không ghi rõ error rate.

### 6. Kết luận

Chia thành:

#### VERIFIED

Có bằng chứng error records đang làm sai metric.

#### NOT VERIFIED

Audit cảnh báo nhưng dữ liệu hiện tại không chứng minh ảnh hưởng.

#### IMPACT

Ví dụ:

"12/100 records là error, nếu loại error thì Recall@10 từ X tăng lên Y."

Không được nói "metric bị sai" nếu implementation thực tế vẫn đúng theo định nghĩa đã chọn.

### 7. Quyết định có sửa hay không

Chỉ đề xuất sửa nếu:

1. implementation hiện tại không đúng với metric definition đã thống nhất;
2. dữ liệu thực tế chứng minh có ảnh hưởng;
3. có thể xác định rõ expected behavior.

Nếu cần sửa, chỉ mô tả patch cần làm.

KHÔNG SỬA CODE ở bước này.

Cuối báo cáo phải có một mục:

`SHOULD FIX: YES / NO / NEED MORE EVIDENCE`

kèm bằng chứng cụ thể.
