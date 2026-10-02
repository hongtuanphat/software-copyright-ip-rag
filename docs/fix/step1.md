Bạn đang làm nhiệm vụ DEBUG/AUDIT cho project `software-copyright-ip-rag`.

Mục tiêu duy nhất của bước này:

> XÁC MINH BẰNG CODE VÀ DỮ LIỆU THỰC TẾ xem lỗi "citation index mismatch khi có distractor" có thực sự xảy ra trong runtime/evaluation hay không, và nếu có thì nó ảnh hưởng đến Citation Exact Match (CEM), citation precision/recall như thế nào.

TUYỆT ĐỐI KHÔNG SỬA CODE trong bước này.

Không được mặc định tin kết luận từ audit trước. Audit chỉ là hypothesis cần kiểm chứng.

### Hypothesis cần kiểm chứng

Audit cho rằng:

* `build_prompt()` đánh số TÀI LIỆU `[1..n]` nhưng bỏ qua distractor.
* `pipeline.py` lại map `used_citations` vào `retrieval_hits_data` chứa cả distractor.
* Nếu distractor nằm xen giữa các hit thì `[i]` mà LLM nhìn thấy không còn tương ứng với `retrieval_hits_data[i-1]`.
* Điều này có thể làm hệ thống ghi nhận `cited_documents` sai dù LLM thực tế đã trích đúng tài liệu.

Audit trước kết luận đây là bug chắc chắn, nhưng chưa chứng minh bằng evaluation data.

### Việc 1 — Trace code thật

Đọc và trace chính xác các function liên quan:

* `build_prompt()`
* `pipeline.py::query()`
* `generation/citation.py`
* `extract_citation_indices()`
* `build_citations()`
* nơi tạo `retrieval_hits`
* nơi tạo `retrieval_hits_data`
* nơi lọc `is_distractor`
* nơi tạo `used_citations`
* nơi tạo `cited_documents`
* `run_CEM.py`
* `runner.py`

Hãy dựng lại chính xác data flow:

retrieval hits
→ filtering
→ prompt document numbering
→ LLM `used_citations`
→ citation mapping
→ `cited_documents`
→ evaluation
→ CEM / citation precision / citation recall.

Không chỉ đọc tên biến. Phải xác định giá trị thực tế của từng biến ở từng bước.

### Việc 2 — Kiểm tra contract của citation index

Xác định chính xác:

1. `[1]` mà LLM nhìn thấy đại diện cho document nào?
2. `[2]` đại diện cho document nào?
3. `used_citations=[1]` sau khi LLM trả về được hiểu là index của:

   * toàn bộ retrieval hits,
   * hay chỉ prompt hits sau khi bỏ distractor?
4. `cited_documents` được lấy từ list nào?
5. Evaluation `run_CEM.py` cuối cùng so sánh citation với list nào?

Nếu có bất kỳ chỗ nào index semantics thay đổi, ghi rõ.

### Việc 3 — Kiểm tra dữ liệu evaluation thực tế

Không được chỉ nói:

> "Nếu distractor nằm xen giữa thì sẽ sai."

Phải tìm các record thực tế trong evaluation results.

Tìm tất cả records có:

* `retrieval_hits` hoặc dữ liệu tương đương chứa distractor;
* đồng thời có `used_citations`;
* đồng thời có `cited_documents` hoặc đủ dữ liệu để reconstruct citation mapping.

Ưu tiên tìm ít nhất 10–15 mẫu thực tế.

Với mỗi mẫu, tạo bảng:

| Query ID | Retrieval hits | Distractor positions | Prompt numbering | LLM used_citations | Pipeline mapped document | Document thực sự tương ứng | Mapping đúng/sai |
| -------- | -------------- | -------------------- | ---------------- | ------------------ | ------------------------ | -------------------------- | ---------------- |

Ví dụ nếu có:

retrieval_hits:

1. Art10
2. DISTRACTOR
3. Art25

prompt chỉ hiển thị:

[1] Art10
[2] Art25

Nếu LLM trả `[2]`, phải kiểm tra:

* document LLM thực sự muốn trích = Art25
* pipeline hiện map `[2]` = retrieval_hits[1] = DISTRACTOR

Chỉ khi dữ liệu thực tế chứng minh điều này mới được kết luận bug đang ảnh hưởng runtime.

### Việc 4 — Reconstruct citation mapping độc lập

Nếu có thể, viết một script/debug function TẠM THỜI chỉ để phân tích dữ liệu.

Không sửa production logic.

Script phải reconstruct hai cách:

A. Mapping hiện tại:
`used_citation → retrieval_hits_data[index-1]`

B. Mapping theo prompt:
`used_citation → prompt_hits[index-1]`

Sau đó so sánh A và B trên toàn bộ evaluation records có distractor.

Báo:

* tổng số record có distractor;
* tổng số citation có thể kiểm tra;
* số citation mapping giống nhau;
* số citation mapping khác nhau;
* tỷ lệ mapping sai;
* số query bị ảnh hưởng;
* nếu có gold IDs: số query CEM hiện fail nhưng mapping theo prompt có thể pass.

### Việc 5 — Kiểm tra hypothesis "12.7% CEM là do lỗi này"

Không được tự kết luận.

Hãy tính hoặc reconstruct:

1. CEM hiện tại.
2. CEM giả lập nếu citation được map theo `prompt_hits`.
3. Citation precision/recall hiện tại.
4. Citation precision/recall giả lập theo `prompt_hits`.

Chỉ sử dụng records đủ dữ liệu. Ghi rõ denominator.

Đặc biệt phải phân biệt:

* lỗi retrieval thật;
* LLM trích sai citation;
* citation mapping sai;
* evaluator đọc citation sai.

### Việc 6 — Kết luận theo bằng chứng

Cuối báo cáo bắt buộc chia thành:

#### VERIFIED — Có bằng chứng runtime/data

Các lỗi thực sự quan sát được.

#### NOT VERIFIED — Chưa chứng minh được

Các hypothesis chưa có đủ dữ liệu.

#### DISPROVED — Audit trước kết luận sai

Nếu có.

#### IMPACT

Định lượng bug này ảnh hưởng bao nhiêu record/citation và metric thay đổi bao nhiêu.

Sau đó trả lời chính xác:

> "Có đủ bằng chứng để sửa #3 ngay không?"

Chỉ trả lời YES nếu dữ liệu thực tế chứng minh mapping sai.

Nếu YES, mô tả chính xác nguyên nhân và expected fix, nhưng VẪN KHÔNG SỬA CODE trong bước này.

Nếu NO, giải thích bằng dữ liệu tại sao chưa nên sửa.

### Quy tắc quan trọng

* Không sửa code.
* Không refactor.
* Không "fix cho chắc".
* Không coi severity P1 trong audit là bằng chứng.
* Không kết luận chỉ dựa trên static code reading.
* Mọi kết luận quan trọng phải có record/query ID hoặc số liệu thực tế hỗ trợ.
* Nếu thiếu dữ liệu, nói rõ thiếu dữ liệu nào.
* Không được tự tạo dữ liệu giả để chứng minh bug.

Output cuối cùng phải là một báo cáo evidence-based, tập trung duy nhất vào citation index mismatch.
