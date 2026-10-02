Bây giờ hãy sửa lỗi này trong project `software-copyright-ip-rag`.

Mục tiêu:

> Có một source of truth duy nhất cho danh sách documents mà LLM nhìn thấy và danh sách documents dùng để map citation.

### Bước 1 — Ghi lại baseline trước khi sửa

Trước khi thay đổi code, xác định evaluation result/baseline hiện tại.

Ghi lại:

* commit hash hiện tại;
* dataset/split;
* số query;
* số query lỗi;
* retrieval Recall@K;
* citation CEM;
* citation precision;
* citation recall;
* các metric refusal nếu có.

Không được chạy một evaluation mới rồi vô tình overwrite baseline.

### Bước 2 — Thiết kế fix tối thiểu

Ưu tiên kiến trúc:

`retrieval_hits`
→ tạo một danh sách `prompt_hits`
→ `prompt_hits` đã loại distractor
→ đánh số `[1..n]`
→ gửi cho LLM
→ LLM trả `used_citations`
→ map `used_citations` vào CHÍNH `prompt_hits`
→ tạo `cited_documents`.

Không được để `build_prompt()` và citation mapping tự lọc/re-index theo hai cách độc lập.

### Bước 3 — Đánh giá `build_citations()`

Kiểm tra implementation hiện tại của:

`generation/citation.py::build_citations()`

Xác định nó có thể trở thành source of truth hay không.

Nếu `build_citations()` đã thực hiện đúng logic mong muốn:

* sử dụng nó thay cho inline citation mapping;
* xóa duplicate inline logic.

Nếu `build_citations()` chưa phù hợp hoàn toàn:

* chỉ sửa tối thiểu để contract rõ ràng;
* không refactor ngoài phạm vi citation bug.

Không được chỉ xóa code cũ mà chưa chứng minh code mới tương đương/correct.

### Bước 4 — Viết hoặc cập nhật test

Phải có test cho ít nhất:

Case A:

* không có distractor.

Case B:

* distractor ở giữa.

Ví dụ:

`[Art10, DISTRACTOR, Art25]`

LLM citation `[2]` phải map đến `Art25`.

Case C:

* nhiều distractor.

Ví dụ:

`[DIST, Art10, DIST, Art25]`

Citation `[1]` → Art10.
Citation `[2]` → Art25.

Case D:

* citation duplicate `[1,1,2]`.

Case E:

* citation out of range.

Case F:

* không có citation.

### Bước 5 — Chạy unit test

Chạy test liên quan citation và toàn bộ test suite nếu thời gian cho phép.

Nếu test fail:

* không bỏ qua;
* xác định nguyên nhân;
* sửa tối thiểu trong phạm vi bug.

### Bước 6 — Chạy evaluation sau sửa

Chạy đúng cùng dataset/config với baseline.

Không đổi đồng thời:

* embedding model;
* retrieval parameters;
* reranker;
* RRF;
* threshold;
* prompt;
* dataset.

Mục đích là cô lập tác động của citation fix.

### Bước 7 — So sánh before/after

Tạo bảng:

| Metric               | Before | After | Delta |
| -------------------- | -----: | ----: | ----: |
| Citation Exact Match |        |       |       |
| Citation Precision   |        |       |       |
| Citation Recall      |        |       |       |
| Recall@1             |        |       |       |
| Recall@5             |        |       |       |
| Recall@10            |        |       |       |
| Error records        |        |       |       |

Ngoài metric tổng thể, kiểm tra riêng:

* các query từng có distractor;
* các query mapping sai ở Prompt 1;
* các query không có distractor.

### Bước 8 — Kiểm tra regression

Đảm bảo fix citation không làm thay đổi retrieval.

Nếu Recall@K thay đổi, phải giải thích tại sao.

Nếu chỉ citation metrics thay đổi mà retrieval giữ nguyên, đó là expected.

### Bước 9 — Kết luận

Chỉ kết luận:

* bug đã được sửa;
* bug đã được xác minh;
* metric thay đổi bao nhiêu;
* những query nào được cải thiện.

Không được tuyên bố "fix thành công" chỉ vì code chạy không lỗi.

Thành công phải được chứng minh bằng:

1. test;
2. evaluation;
3. before/after;
4. regression check.

Cuối cùng ghi rõ:

* files changed;
* logic changed;
* tests added/changed;
* evaluation result;
* commit hash mới nếu có.

Không sửa bất kỳ vấn đề audit nào khác trong bước này.
