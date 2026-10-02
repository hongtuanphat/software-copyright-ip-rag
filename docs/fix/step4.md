Tiếp tục audit project `software-copyright-ip-rag`.

Mục tiêu:

> Xác minh chính xác production Webapp, CLI và evaluation đang sử dụng retrieval/reranker pipeline nào, có thực sự đo cùng một hệ thống hay không.

KHÔNG sửa code trong bước này.

Không được mặc định rằng "ENABLE_RERANKER=True" có nghĩa tất cả evaluation đều đang dùng cùng reranker.

### 1. Trace production Webapp

Trace:

`webapp/app.py`
→ `answer_rag()`
→ `get_pipeline()`
→ `RAGPipeline`
→ `query()`
→ retrieval
→ reranker
→ decide
→ generation.

Ghi lại:

* retrieval mode;
* initial retrieval K;
* reranker input K;
* final K;
* reranker model;
* score threshold;
* distractor filtering;
* thứ tự các bước.

### 2. Trace CLI

Trace:

`main.py`
→ `answer_question()`

Xác định:

* có reranker hay không;
* nếu không thì retrieval output khác production ở đâu;
* CLI có thực sự được xem là production entry point hay chỉ là debug/test tool.

Không được tự quyết định "main.py phải sửa" nếu chưa xác định mục đích của nó.

### 3. Trace evaluation

Đặc biệt:

`run_recall.py`

và

`run_all.py`

Xác định từng system:

* Dense
* BM25
* Hybrid
* Hybrid + Reranker nếu có

đang gọi function nào.

Tạo bảng:

| System | Entry point | Retriever | Initial K | Reranker | Final K | Production-equivalent? |
| ------ | ----------- | --------- | --------: | -------- | ------: | ---------------------- |

### 4. Kiểm tra configuration thực tế

Tìm giá trị thực tế của:

* `ENABLE_RERANKER`
* `RERANKER_INPUT_K`
* `TOP_K`
* `RRF_K`
* `reranker_model_name`
* `reranker_max_length`
* `MIN_SCORE_TIN_CAY`

Không chỉ đọc default trong function signature.

Xác định config cuối cùng được load khi chạy evaluation.

### 5. Kiểm tra metadata

Xem evaluation result có ghi:

* enable_reranker;
* reranker model;
* input K;
* final K;
* retrieval mode.

Nếu thiếu, ghi rõ thiếu metadata nào.

### 6. Thiết kế controlled experiment

Không sửa code.

Chạy/thiết kế một experiment giữ mọi thứ cố định:

Baseline:

`Hybrid WITHOUT reranker`

Experiment:

`Hybrid WITH reranker`

Giữ nguyên:

* dataset;
* questions;
* embedding;
* BM25;
* RRF;
* threshold;
* TOP_K;
* prompt;
* LLM.

Chỉ thay:

`ENABLE_RERANKER`.

Sau đó so sánh:

* Recall@1
* Recall@5
* Recall@10
* Recall@20
* article recall nếu có.

### 7. Quan trọng: kiểm tra reranker có thật sự thay đổi ranking

Không chỉ nhìn metric.

Chọn một số query có:

* ranking thay đổi;
* ranking không thay đổi;
* gold document được đẩy lên;
* gold document bị đẩy xuống.

Tạo bảng:

| Query | Gold | Hybrid rank | Reranker rank | Change |
| ----- | ---- | ----------: | ------------: | -----: |

### 8. Kết luận

Phải phân biệt:

* production mismatch;
* evaluation mismatch;
* CLI mismatch;
* chỉ là tool debug khác production và không phải bug.

Không được tự kết luận "reranker tốt hơn".

Chỉ báo cáo:

> Reranker làm thay đổi metric X từ A → B trên dataset Y.

Nếu metric giảm thì cũng ghi nhận đúng như vậy.

### 9. Quyết định sửa

Cuối cùng:

`SHOULD FIX PRODUCTION/EVALUATION CONSISTENCY: YES / NO / NEED MORE EVIDENCE`

Nếu YES:

* chỉ rõ entry point nào cần thay đổi;
* expected behavior;
* test cần có.

Không sửa code trong bước này.
