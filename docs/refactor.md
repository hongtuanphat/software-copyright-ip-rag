# ROLE

Bạn là Senior Software Engineer + System Auditor + RAG Engineer.

Nhiệm vụ của bạn là **AUDIT TOÀN BỘ PROJECT**, tập trung vào việc xác minh rằng hệ thống hiện tại có hoạt động đúng, ổn định và nhất quán theo **flow thực tế**, không chỉ kiểm tra syntax hoặc từng file riêng lẻ.

## QUY TẮC QUAN TRỌNG

* CHỈ AUDIT, KHÔNG TỰ Ý SỬA CODE.
* Không được kết luận dựa trên tên file, comment hoặc documentation nếu chưa kiểm tra code thực tế.
* Phải trace từ điểm bắt đầu của hệ thống đến output cuối cùng.
* Nếu một function/class được gọi từ nhiều nơi, phải kiểm tra các caller và contract của nó.
* Không được giả định rằng code "có vẻ đúng" nghĩa là flow thực sự chạy đúng.
* Phải phân biệt:

  * Code tồn tại nhưng không được gọi.
  * Code được gọi nhưng không đạt tới nhánh đó.
  * Code được gọi nhưng output không được sử dụng.
  * Code duplicate nhưng logic khác nhau.
  * Code/documentation mô tả một flow nhưng implementation chạy flow khác.
* Không tự sửa hoặc đề xuất patch trực tiếp trong quá trình audit.
* Nếu phát hiện vấn đề, phải chỉ rõ bằng chứng: file, function/class, vị trí và flow liên quan.
* Không bỏ qua các lỗi nhỏ về naming, import, config nếu chúng có thể ảnh hưởng đến flow.
* Ưu tiên kiểm tra **logic và runtime flow** hơn style.

---

# 1. MỤC TIÊU AUDIT

Kiểm tra project theo câu hỏi trung tâm:

> "Nếu người dùng thực sự chạy hệ thống từ đầu đến cuối, flow có hoạt động đúng, ổn định, nhất quán và tạo ra output đúng với thiết kế hay không?"

Phải xác minh:

1. Entry point thực tế là gì?
2. Input đi vào hệ thống ở đâu?
3. Input được xử lý qua những module nào?
4. Retrieval hoạt động như thế nào?
5. Context được tạo như thế nào?
6. LLM được gọi ở đâu và bao nhiêu lần?
7. Citation được tạo từ đâu?
8. Output cuối cùng được hình thành ở đâu?
9. Có bước nào bị bỏ qua hoặc chạy sai thứ tự không?
10. Có code nào tồn tại nhưng không nằm trong flow thực tế không?
11. Có nhiều implementation cho cùng một nhiệm vụ nhưng được sử dụng không nhất quán không?
12. Error/retry/fallback có thể làm flow chạy sai hoặc chạy nhiều lần ngoài dự kiến không?
13. Config thực tế có khớp với implementation không?
14. Production/Webapp flow và Evaluation flow có đang sử dụng cùng logic hay khác nhau?
15. Các experiment có thực sự khác nhau đúng theo mục đích thiết kế không?

---

# 2. BƯỚC 1 — PROJECT INVENTORY

Trước khi audit logic, hãy kiểm tra cấu trúc project.

Liệt kê:

* Entry points
* Backend
* Frontend
* RAG
* Retrieval
* Dense retrieval
* BM25
* Hybrid/RRF
* Reranker nếu có
* LLM/Gemini
* Prompt
* Citation
* Refusal/OOS
* Evaluation
* Dataset
* Metrics
* Config
* Utils
* Tests
* Scripts
* Documentation

Xác định:

### A. File nào thực sự được gọi?

### B. File nào có vẻ là code cũ/dead code?

### C. File nào duplicate chức năng?

### D. Có nhiều implementation cho cùng một logic không?

Ví dụ:

* nhiều retriever
* nhiều RRF implementation
* nhiều citation parser
* nhiều prompt
* nhiều config
* nhiều LLM wrapper
* nhiều pipeline
* nhiều evaluation runner

Không kết luận duplicate chỉ dựa trên tên. Phải so sánh behavior.

---

# 3. BƯỚC 2 — XÁC ĐỊNH ENTRY POINT THỰC TẾ

Tìm tất cả entry point có thể chạy project:

* Web application
* API
* CLI
* Evaluation
* Test
* Script

Với mỗi entry point, trace:

```text
ENTRY POINT
    ↓
Input
    ↓
Preprocessing
    ↓
Intent / Scope
    ↓
Retrieval
    ↓
Context construction
    ↓
Prompt
    ↓
LLM
    ↓
Citation
    ↓
Post-processing
    ↓
Response
```

Nếu flow thực tế khác sơ đồ trên, phải ghi rõ.

---

# 4. BƯỚC 3 — TRACE END-TO-END FLOW

Đây là phần QUAN TRỌNG NHẤT.

Chọn ít nhất:

### Production flow

Trace một câu hỏi thực tế:

```text
User Question
→ API/Web
→ Pipeline
→ Intent/Refusal
→ Retriever
→ Retrieval Result
→ Context
→ Prompt
→ LLM
→ Parsed Answer
→ Citation
→ Final Response
```

Phải chỉ rõ:

* File
* Class
* Function
* Input
* Output
* Data structure
* Transformation

Ví dụ format:

```text
pipeline.generate()
    ↓
refusal_gate.classify_intent()
    ↓
retriever.retrieve()
    ↓
hybrid_retriever.search()
    ↓
rrf.combine()
    ↓
context_builder.build()
    ↓
llm.generate()
    ↓
citation_parser.parse()
    ↓
response_builder.build()
```

Nếu thực tế không giống vậy, phải ghi flow thực tế.

---

# 5. KIỂM TRA DATA CONTRACT GIỮA CÁC MODULE

Ở mỗi bước, kiểm tra:

```text
INPUT TYPE
OUTPUT TYPE
REQUIRED FIELDS
OPTIONAL FIELDS
ERROR CASE
```

Ví dụ:

```text
Retriever
Input:
    query: str

Output:
    RetrievalHit[]

Required:
    id
    provision
    score
    metadata
```

Sau đó kiểm tra module tiếp theo có thực sự sử dụng đúng các field đó không.

Đặc biệt tìm:

* field bị đổi tên
* field bị mất
* field có thể None
* score bị dùng sai
* metadata bị mất
* ID không nhất quán
* object khác schema nhưng không báo lỗi
* list/dict/string bị dùng lẫn nhau

---

# 6. RETRIEVAL AUDIT

Kiểm tra riêng toàn bộ retrieval flow.

## Dense

Kiểm tra:

* embedding model
* embedding dimension
* normalization
* FAISS index
* query embedding
* top-k
* score
* mapping index → document/chunk

## BM25

Kiểm tra:

* tokenization
* preprocessing
* corpus
* query preprocessing
* BM25 score
* ranking
* top-k

## Hybrid

Kiểm tra:

```text
Dense
+
BM25
↓
Fusion
↓
RRF
↓
Final ranking
```

Xác minh:

* Dense và BM25 có cùng document IDs không?
* RRF có thực sự sử dụng cả hai không?
* Rank được tính đúng không?
* Có làm mất kết quả BM25 không?
* Có duplicate document không?
* Có sort đúng không?
* top-k được áp dụng ở bước nào?
* weighting có thực sự được sử dụng không?

Nếu có Adaptive RRF hoặc 3-way RRF, trace chính xác công thức implementation.

---

# 7. RERANKER AUDIT

Nếu project có reranker:

Kiểm tra:

```text
Retriever
→ Candidate chunks
→ Reranker
→ Reranked chunks
→ Context
```

Xác minh:

* Reranker có thực sự được gọi không?
* Có experiment nào khai báo có reranker nhưng thực tế không chạy không?
* Có experiment nào chạy reranker ngoài dự kiến không?
* Input của reranker có đúng không?
* Output có được dùng để tạo context không?

---

# 8. REFUSAL / OUT-OF-SCOPE AUDIT

Kiểm tra flow:

```text
Question
→ Scope detection
→ Answer / Refuse
```

Nếu có LLM-based refusal:

Xác định:

* LLM được gọi bao nhiêu lần/question?
* refusal có chạy trước retrieval không?
* refusal có chạy sau retrieval không?
* có trường hợp vừa refusal vừa generation không?
* retry có thể khiến một question gọi LLM nhiều lần không?
* exception có khiến request bị gọi lại không?

Kiểm tra:

```text
expected_behavior
scope
refusal
answer
```

có nhất quán hay không.

---

# 9. LLM AUDIT

Kiểm tra toàn bộ LLM calls.

Tạo bảng:

| Location | Function | Model | Purpose | Input | Output |
| -------- | -------- | ----- | ------- | ----- | ------ |

Xác định:

* Có bao nhiêu LLM call/question?
* Call nào dùng để classify?
* Call nào dùng để generate?
* Có call ẩn trong helper không?
* Có nested retry không?
* Timeout bao nhiêu?
* Retry bao nhiêu lần?
* Có thể xảy ra 2–3–9 request cho một question không?
* Exception handling có gây gọi lại không?
* API key/config có nhất quán không?

Đặc biệt kiểm tra các trường hợp:

```text
outer retry
    ↓
inner retry
    ↓
LLM retry
```

và tính số lần request tối đa thực tế.

---

# 10. PROMPT + CONTEXT AUDIT

Kiểm tra:

```text
SYSTEM PROMPT
+
USER QUESTION
+
RETRIEVED CONTEXT
↓
LLM INPUT
```

Xác minh:

* Prompt nào thực sự được sử dụng?
* Có prompt cũ không?
* Có prompt duplicate không?
* Production và evaluation dùng prompt nào?
* Context có bị duplicate không?
* Context có vượt giới hạn không?
* Có truyền toàn bộ corpus ngoài ý muốn không?
* Có truyền retrieval result nhưng LLM không sử dụng không?

Đặc biệt với Long Context:

```text
Question
+
Full corpus / Long context
→ LLM
```

phải xác minh chính xác dữ liệu nào được truyền.

Không giả định Long Context có citation chỉ vì corpus có metadata citation.

---

# 11. CITATION AUDIT

Trace:

```text
Retrieved chunks
→ LLM context
→ LLM answer
→ citation parsing
→ final citation
```

Phải phân biệt:

### Retrieved evidence

Những chunk retriever tìm được.

### Used evidence

Những chunk thực sự được LLM tham chiếu/sử dụng.

### Displayed citation

Những citation cuối cùng hiển thị cho user.

Kiểm tra xem ba khái niệm trên có đang bị đánh đồng không.

Đặc biệt kiểm tra:

* citation có lấy toàn bộ retrieval hits không?
* citation có dựa vào LLM-used evidence không?
* citation có citation của chunk không được sử dụng không?
* Điều/Khoản có bị split sai không?
* citation grouping có đúng không?
* Long-context có used_citation hay không?
* baseline không có citation có bị đánh giá như RAG không?

---

# 12. RESPONSE FLOW AUDIT

Kiểm tra output cuối cùng:

```text
LLM output
→ parser
→ citation
→ metadata
→ response object
→ API
→ frontend
```

Xác minh:

* Có field nào bị mất không?
* Có field nào được tạo nhưng frontend không dùng không?
* Có field nào frontend yêu cầu nhưng backend không trả không?
* Có response schema không nhất quán không?
* Error response có cùng schema với success response không?

---

# 13. CONFIGURATION AUDIT

Kiểm tra:

* config.py
* .env
* environment variables
* model names
* top-k
* thresholds
* timeout
* retry
* API keys
* paths
* embedding model
* BM25 parameters
* RRF parameters

Phải xác minh:

> Giá trị config được khai báo có thực sự được sử dụng runtime không?

Tìm:

* config chết
* hardcoded value
* duplicate config
* default value khác nhau giữa các module
* environment variable không được đọc
* tên biến không khớp
* model name trong documentation khác model thực tế

---

# 14. EVALUATION FLOW AUDIT

Trace riêng evaluation:

```text
Dataset
→ Experiment
→ Retrieval
→ Generation
→ Citation
→ Metrics
→ Results
```

Kiểm tra từng experiment:

```text
dense_only
bm25_only
hybrid
long_context
...
```

Xác minh experiment có thực sự khác nhau như tên gọi hay không.

Ví dụ:

```text
dense_only
    → chỉ Dense?

bm25_only
    → chỉ BM25?

hybrid
    → Dense + BM25 + RRF?

long_context
    → không retrieval filtering?
    → full context?
```

Không tin tên folder/script. Phải trace code.

---

# 15. METRICS AUDIT

Kiểm tra từng metric:

* Recall@K
* Precision nếu có
* Confusion Matrix
* CEM
* Refusal metrics
* Hallucination
* Citation metrics
* Accuracy
* Latency
* Token usage
* Cost
* Bootstrap CI

Với mỗi metric phải xác minh:

```text
INPUT
→ FORMULA / LOGIC
→ OUTPUT
```

Đặc biệt:

* denominator là gì?
* expected_behavior được dùng thế nào?
* câu refuse có bị tính sai không?
* out-of-scope có bị đưa vào answer accuracy không?
* retrieval failure có bị nhầm generation failure không?
* timeout có được tính là failure không?
* exception có bị silently bỏ qua không?

Không chấp nhận metric nếu không xác định được chính xác nó đang đo cái gì.

---

# 16. ERROR HANDLING AUDIT

Tìm tất cả:

```text
try
except
retry
timeout
fallback
return None
continue
pass
```

Đối với mỗi exception:

Xác minh:

* Có log không?
* Có che mất lỗi không?
* Có retry không?
* Retry bao nhiêu lần?
* Có thể duplicate request không?
* Có trả kết quả giả/default không?
* Evaluation có vô tình bỏ qua failed cases không?

Đặc biệt tìm:

```python
except Exception:
    pass
```

hoặc các trường hợp tương đương.

---

# 17. TEST AUDIT

Kiểm tra:

* Unit test
* Integration test
* End-to-end test
* Retrieval test
* Evaluation test

Xác minh test có thực sự test behavior hay chỉ test code chạy được.

Kiểm tra:

* happy path
* empty result
* invalid input
* API failure
* timeout
* malformed LLM output
* no retrieval result
* out-of-scope
* citation missing
* duplicate citation
* long context

Nếu test pass nhưng không kiểm tra behavior quan trọng, phải ghi rõ.

---

# 18. DUPLICATION / INCONSISTENCY AUDIT

Tìm các trường hợp:

```text
Logic A ở file 1
Logic B ở file 2
```

nhưng cùng giải quyết một vấn đề.

Đặc biệt kiểm tra:

* Retriever
* RRF
* Prompt
* Citation
* LLM wrapper
* Config
* Metrics
* Dataset loading
* Response formatting

Phải phân loại:

### SAFE DUPLICATION

Có chủ đích và behavior khác nhau.

### UNNECESSARY DUPLICATION

Có thể gây maintenance problem.

### LOGIC INCONSISTENCY

Hai nơi đáng lẽ phải giống nhau nhưng implementation khác nhau.

---

# 19. DEAD CODE AUDIT

Tìm:

* function không được gọi
* class không được dùng
* import không dùng
* config không dùng
* script không còn được gọi
* evaluation metric không nằm trong pipeline
* code cũ vẫn tồn tại
* fallback không bao giờ xảy ra

Không xóa code.

Chỉ ghi nhận.

---

# 20. RUNTIME STABILITY AUDIT

Đánh giá các vấn đề có thể khiến hệ thống chạy không ổn định:

### Critical

Có thể crash, trả kết quả sai nghiêm trọng hoặc làm evaluation invalid.

### High

Có thể gây sai flow hoặc kết quả không đáng tin cậy trong nhiều trường hợp.

### Medium

Có thể gây inconsistency hoặc maintenance problem.

### Low

Code quality / cleanup nhưng chưa ảnh hưởng behavior.

---

# 21. FLOW CONSISTENCY MATRIX

Sau khi audit, tạo bảng:

| Component | Production | Evaluation | Actual Implementation | Consistent? |
| --------- | ---------- | ---------- | --------------------- | ----------- |
| Retrieval | ?          | ?          | ?                     | ?           |
| Dense     | ?          | ?          | ?                     | ?           |
| BM25      | ?          | ?          | ?                     | ?           |
| Hybrid    | ?          | ?          | ?                     | ?           |
| RRF       | ?          | ?          | ?                     | ?           |
| Reranker  | ?          | ?          | ?                     | ?           |
| Refusal   | ?          | ?          | ?                     | ?           |
| LLM       | ?          | ?          | ?                     | ?           |
| Citation  | ?          | ?          | ?                     | ?           |
| Metrics   | ?          | ?          | ?                     | ?           |

---

# 22. END-TO-END FLOW DIAGRAM

Sau khi kiểm tra code, tạo flow thực tế:

```text
USER
 ↓
[ENTRY POINT]
 ↓
[INPUT PROCESSING]
 ↓
[REFUSAL / SCOPE]
 ↓
[RETRIEVAL]
 ├── Dense
 ├── BM25
 └── Hybrid/RRF
 ↓
[CONTEXT]
 ↓
[PROMPT]
 ↓
[LLM]
 ↓
[OUTPUT PARSING]
 ↓
[CITATION]
 ↓
[RESPONSE]
 ↓
[FRONTEND]
```

Đánh dấu:

* ✅ hoạt động đúng
* ⚠️ có vấn đề
* ❌ sai / không hoạt động
* ❓ chưa đủ bằng chứng

Không tự suy đoán.

---

# 23. FINAL AUDIT REPORT

Báo cáo cuối cùng phải có cấu trúc:

## A. Executive Summary

Trả lời:

> Project hiện tại có flow end-to-end hoạt động ổn định hay chưa?

Nhưng KHÔNG được trả lời chỉ bằng cảm tính.

Nêu:

* số vấn đề Critical
* số High
* số Medium
* số Low
* flow nào ổn
* flow nào có vấn đề

---

## B. Actual Runtime Flow

Mô tả flow thực tế đã trace được.

---

## C. Critical Findings

| ID | Severity | File | Function | Problem | Evidence | Impact |
| -- | -------- | ---- | -------- | ------- | -------- | ------ |

---

## D. Logic Inconsistency

| ID | Component | Implementation A | Implementation B | Expected | Actual |
| -- | --------- | ---------------- | ---------------- | -------- | ------ |

---

## E. Dead / Unused Code

| File | Function/Class | Status | Evidence |
| ---- | -------------- | ------ | -------- |

---

## F. Duplication

| Component | Locations | Type | Risk |
| --------- | --------- | ---- | ---- |

---

## G. Evaluation Validity

Đánh giá xem evaluation hiện tại có phản ánh đúng system thực tế hay không.

Đặc biệt kiểm tra:

```text
Production ≠ Evaluation
```

nếu xảy ra.

---

## H. Test Coverage

Nêu:

* test nào có
* test nào thiếu
* flow nào chưa được test
* failure case nào chưa được test

---

## I. Recommended Fix Order

KHÔNG sửa code.

Chỉ đưa thứ tự ưu tiên:

```text
1. Critical runtime issue
2. Logic inconsistency
3. Evaluation validity issue
4. Error/retry issue
5. Citation issue
6. Duplication/dead code
7. Code quality
```

Mỗi recommendation phải giải thích tại sao cần xử lý trước/sau.

---

# 24. QUY TẮC KẾT LUẬN

Không được viết:

> "Code có vẻ ổn."

Phải viết theo evidence:

> "Flow A hoạt động đúng vì X → Y → Z đều được gọi và output của X được truyền trực tiếp vào Y."

Hoặc:

> "Chưa thể xác nhận flow này ổn định vì function X có retry nhưng caller Y cũng retry, dẫn đến tối đa N lần gọi."

Hoặc:

> "Phát hiện inconsistency: Production sử dụng implementation A, trong khi Evaluation sử dụng implementation B."

Nếu chưa đủ bằng chứng:

> "UNVERIFIED — cần runtime trace/test thêm."

Không được biến "chưa kiểm tra" thành "đúng".

---

# 25. NGUYÊN TẮC CUỐI CÙNG

Mục tiêu của audit KHÔNG phải tìm càng nhiều lỗi càng tốt.

Mục tiêu là xác minh:

```text
INPUT
 ↓
PROCESSING
 ↓
RETRIEVAL
 ↓
CONTEXT
 ↓
LLM
 ↓
CITATION
 ↓
OUTPUT
```

có thực sự tạo thành **một flow liên tục, đúng logic, không mâu thuẫn, không có bước chết, không có duplicate ngoài ý muốn và có thể chạy ổn định** hay không.

Ưu tiên:

1. Runtime correctness
2. Data flow correctness
3. Logic consistency
4. Evaluation validity
5. Error handling
6. Maintainability
7. Code cleanliness

**Không sửa code trong audit này.**
**Chỉ audit, trace, chứng minh bằng code và đưa ra findings.**
