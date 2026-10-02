# BƯỚC 7: PHÂN TÍCH CHUYÊN SÂU & ĐỘ TIN CẬY

## 1. Mục tiêu

Hoàn thiện hệ thống Evaluation theo hướng có thể:

* Phân tích kết quả chi tiết theo từng nhóm câu hỏi.
* Định lượng mức độ không chắc chắn của các metric thông qua khoảng tin cậy 95%.
* Lưu đầy đủ dữ liệu thực thi để phục vụ Error Analysis.
* Xác định nguyên nhân lỗi dựa trên bằng chứng từ pipeline và log thực tế, thay vì suy đoán từ nhãn dữ liệu.
* Phân tích độ trễ dựa trên các thành phần thực tế của hệ thống như Retrieval, LLM/API và cơ chế Retry.
* Cung cấp đầy đủ số liệu để cập nhật báo cáo một cách nhất quán với kết quả thực nghiệm.

---

# 2. CODE CẦN SỬA

## 2.1. Phân rã kết quả theo nhóm câu hỏi (Group Breakdown)

Bổ sung khả năng tổng hợp kết quả theo từng nhóm thay vì chỉ tính metric trên toàn bộ 100 câu.

### Retrieval Evaluation

Tính riêng cho:

* Nhóm 1
* Nhóm 2
* Nhóm 3

Các metric cần hỗ trợ:

* Recall@1
* Recall@3
* Recall@5
* Recall@10

Có thể thống kê theo cả Clause-level và Article-level nếu hệ thống hiện tại hỗ trợ hai mức đánh giá này.

### Refusal Evaluation

Tính riêng cho:

* Nhóm 4
* Nhóm 5a
* Nhóm 5b
* Nhóm 5c
* Nhóm 5d

Các metric cần xuất gồm:

* TP
* TN
* FP
* FN
* TRR hoặc metric từ chối đang được định nghĩa chính thức trong hệ thống.

Kết quả phải được tính trực tiếp từ dữ liệu thực thi, không hard-code giá trị.

---

## 2.2. Lưu kết quả chi tiết theo từng câu

Evaluation cần lưu được kết quả ở cấp độ từng question để phục vụ phân tích lỗi.

Tùy từng pipeline, record kết quả nên chứa các thông tin phù hợp như:

* `question_id`
* `group`
* `scope`
* `expected_behavior`
* `predicted_behavior`
* `is_correct`
* `gold_ids`
* `retrieved_ids`
* `retrieval_scores`
* `threshold`
* `latency`
* `input_tokens`
* `output_tokens`
* `retry_count`
* trạng thái API/error nếu có.

Không được tạo dữ liệu giả cho các trường mà pipeline thực tế không đo được.

---

## 2.3. Tính khoảng tin cậy 95% (95% Confidence Interval)

Tích hợp `scipy.stats.bootstrap` để ước lượng khoảng tin cậy 95% cho các metric phù hợp.

Đối với các metric dựa trên kết quả từng câu như Accuracy/CEM hoặc các metric có thể biểu diễn dưới dạng kết quả nhị phân, sử dụng phương pháp bootstrap với:

* Dữ liệu đầu vào: kết quả của các câu hỏi thực tế.
* Số lần resampling: 1.000 lần.
* Confidence level: 95%.

Kết quả cần lưu:

```text
metric
point_estimate
ci_lower
ci_upper
confidence_level
n_resamples
sample_size
```

Ví dụ:

```text
Accuracy = 87.0%
95% CI = [80.2%, 92.5%]
```

Không bắt buộc áp dụng cùng một phương pháp bootstrap cho mọi metric. Các metric như latency cần được xử lý theo đặc trưng phân phối của chính metric đó.

---

## 2.4. Bổ sung Error Analysis dựa trên dữ liệu thực tế

Không sử dụng trực tiếp nhãn `distractor` trong dataset làm nguyên nhân của lỗi.

Nhãn `distractor` chỉ được xem là đặc điểm/phân loại của dữ liệu. Nguyên nhân lỗi phải được xác định từ bằng chứng của pipeline.

Đối với các trường hợp trả lời sai hoặc từ chối sai, cần kiểm tra các yếu tố như:

* Retrieval có tìm được `gold_ids` hay không.
* Điểm retrieval cao nhất/thấp nhất.
* Kết quả có bị loại bởi threshold hay không.
* Threshold đang sử dụng là bao nhiêu.
* LLM nhận được context nào.
* LLM có trả lời/refuse đúng expected behavior hay không.
* Có xảy ra lỗi API hay Retry hay không.
* Có lỗi ở bước hậu xử lý/citation hay không.

Có thể phân loại lỗi thành các nhóm:

```text
Retrieval Error
Threshold Error
Generation Error
Scope/Refusal Error
Citation Error
API/Network Error
Other/Unknown
```

Chỉ gán nguyên nhân khi có evidence phù hợp. Nếu chưa đủ dữ liệu thì ghi `Unknown/Insufficient Evidence`, không suy đoán.

---

## 2.5. Bổ sung log phân tích Latency

Hệ thống cần lưu dữ liệu để xác định nguồn gây ra độ trễ.

Tối thiểu cần phân biệt:

* Tổng thời gian xử lý.
* Thời gian Retrieval nếu đo được.
* Thời gian gọi LLM/API nếu đo được.
* Số lần Retry.
* Số lần API attempt.
* Trạng thái lỗi API nếu có.

Đặc biệt, không được quy kết độ trễ cho một thành phần không tồn tại trong pipeline thực tế, ví dụ Reranker nếu hệ thống hiện tại không sử dụng Reranker.

Nếu một request mất 35 giây và log cho thấy có nhiều lần Retry khi gọi API, báo cáo có thể phân tích trường hợp này dựa trên bằng chứng đó.

---

## 2.6. Bổ sung Performance Metrics

Đối với Performance Evaluation, hệ thống cần thu thập nếu đo được đáng tin cậy:

* Latency median.
* Latency p95.
* Input Tokens.
* Output Tokens.
* Cost, nếu API/provider cung cấp thông tin đủ tin cậy để tính.

Không tạo giá trị `0` hoặc giá trị giả khi metric không đo được. Trường hợp không có dữ liệu phải ghi rõ `N/A` hoặc `Not Available`.

---

# 3. BÁO CÁO CẦN SỬA

## 3.1. Bổ sung bảng Recall theo nhóm

Báo cáo cần có bảng riêng thể hiện kết quả Retrieval theo:

* Nhóm 1
* Nhóm 2
* Nhóm 3

Ví dụ cấu trúc:

| Nhóm   | Số câu | Recall@1 | Recall@3 | Recall@5 | Recall@10 |
| ------ | -----: | -------: | -------: | -------: | --------: |
| Nhóm 1 |    ... |      ... |      ... |      ... |       ... |
| Nhóm 2 |    ... |      ... |      ... |      ... |       ... |
| Nhóm 3 |    ... |      ... |      ... |      ... |       ... |

Nếu đánh giá ở hai mức Clause-level và Article-level thì trình bày riêng hai bảng hoặc hai phần rõ ràng.

---

## 3.2. Bổ sung bảng TRR theo nhóm

Báo cáo cần thể hiện kết quả từ chối theo:

* Nhóm 4
* Nhóm 5a
* Nhóm 5b
* Nhóm 5c
* Nhóm 5d

Ví dụ:

| Nhóm    | Số câu |  TP |  TN |  FP |  FN | TRR |
| ------- | -----: | --: | --: | --: | --: | --: |
| Nhóm 4  |    ... | ... | ... | ... | ... | ... |
| Nhóm 5a |    ... | ... | ... | ... | ... | ... |
| Nhóm 5b |    ... | ... | ... | ... | ... | ... |
| Nhóm 5c |    ... | ... | ... | ... | ... | ... |
| Nhóm 5d |    ... | ... | ... | ... | ... | ... |

---

## 3.3. Bổ sung khoảng tin cậy 95%

Các metric chính có thể được trình bày kèm khoảng tin cậy, ví dụ:

```text
Accuracy: 87.0%
95% CI: [80.2%, 92.5%]
```

Hoặc trong bảng:

| System        | Accuracy | 95% CI |
| ------------- | -------: | -----: |
| Gemini No-RAG |      ... |  [...] |
| Hybrid RAG    |      ... |  [...] |

Không sử dụng một giá trị `±` cố định nếu khoảng tin cậy thực tế chưa được tính từ dữ liệu.

---

## 3.4. Viết lại phần Error Analysis

Không đưa ra kết luận như:

> "80% lỗi do Distractor"

chỉ dựa trên nhãn `distractor` được gán thủ công.

Thay vào đó, phân tích từng nhóm lỗi dựa trên evidence từ evaluation.

Ví dụ:

| Loại lỗi         | Số lượng | Tỷ lệ | Evidence                                  |
| ---------------- | -------: | ----: | ----------------------------------------- |
| Retrieval Error  |      ... |   ... | Gold document không xuất hiện trong Top-K |
| Threshold Error  |      ... |   ... | Kết quả bị loại bởi threshold             |
| Generation Error |      ... |   ... | Context đúng nhưng câu trả lời sai        |
| API/Retry Error  |      ... |   ... | Có Retry/API error trong log              |
| Unknown          |      ... |   ... | Chưa đủ evidence                          |

Phần nhận xét phải phân biệt rõ:

* **Kết quả quan sát được**
* **Nguyên nhân được chứng minh bằng log**
* **Giả thuyết chưa đủ bằng chứng**

---

## 3.5. Viết lại phần phân tích Latency

Không quy kết độ trễ cho Reranker hoặc thành phần khác nếu thành phần đó không tồn tại trong pipeline.

Thay vào đó, báo cáo dựa trên:

* Median latency.
* P95 latency.
* Retrieval latency nếu có.
* LLM/API latency nếu có.
* Retry count.
* API error/timeout nếu có.

Ví dụ cách trình bày:

> Một số truy vấn có độ trễ cao được đối chiếu với log thực thi để xác định thành phần đóng góp vào thời gian xử lý. Các trường hợp có nhiều lần gọi lại API được xem xét riêng nhằm phân biệt độ trễ do cơ chế Retry/API với độ trễ của pipeline Retrieval.

---

# 4. KẾT QUẢ NGHIỆM THU

Bước 7 được xem là hoàn thành khi:

### Về Code

* [ ] Có kết quả chi tiết theo từng câu hỏi.
* [ ] Có Recall theo Nhóm 1, 2, 3.
* [ ] Có TRR theo Nhóm 4, 5a, 5b, 5c, 5d.
* [ ] Có 95% CI cho các metric phù hợp.
* [ ] Bootstrap sử dụng 1.000 lần resampling.
* [ ] Có dữ liệu phục vụ Error Analysis.
* [ ] Có log Retry/API nếu pipeline có sử dụng cơ chế Retry.
* [ ] Có Latency median và p95 khi thực hiện Performance Evaluation.
* [ ] Input/Output Tokens được ghi nhận nếu provider hỗ trợ.
* [ ] Cost chỉ được tính khi có dữ liệu đáng tin cậy.
* [ ] Không hard-code kết quả.
* [ ] Không tạo dữ liệu giả cho các trường chưa đo được.
* [ ] Không quy kết lỗi dựa trên nhãn `distractor` nếu không có evidence từ pipeline.

### Về Báo cáo

* [ ] Có bảng Recall riêng cho Nhóm 1, 2, 3.
* [ ] Có bảng TRR riêng cho Nhóm 4, 5a, 5b, 5c, 5d.
* [ ] Có khoảng tin cậy 95% cho các metric phù hợp.
* [ ] Error Analysis dựa trên dữ liệu thực tế.
* [ ] Phân tích Latency dựa trên log thực thi.
* [ ] Không đề cập đến thành phần không tồn tại trong pipeline.
* [ ] Mọi số liệu trong báo cáo khớp với file kết quả Evaluation.
* [ ] Các kết luận về nguyên nhân lỗi phải có evidence tương ứng.

**Nguyên tắc cuối cùng:** Code có nhiệm vụ **đo lường và lưu bằng chứng**; báo cáo có nhiệm vụ **trình bày và phân tích bằng chứng đó**. Không sửa code hoặc báo cáo theo hướng tạo ra một kết luận đã định trước.
