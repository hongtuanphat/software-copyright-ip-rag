# Chatbot tra cứu quyền tác giả đối với chương trình máy tính

## 1. Tổng quan dự án (Project Overview)

Đây là một hệ thống RAG dùng để tra cứu pháp luật Việt Nam về quyền tác giả đối với chương trình máy tính. Hệ thống tiếp nhận câu hỏi, tìm các đoạn luật liên quan trong kho dữ liệu, kiểm tra câu hỏi có thuộc phạm vi hỗ trợ hay không, sau đó có thể gọi Google Gemini để tạo câu trả lời kèm căn cứ được sử dụng.

Kho dữ liệu hiện có gồm:

- Văn bản hợp nhất số 67/VBHN-VPQH.
- Nghị định số 17/2023/NĐ-CP.
- Nghị định số 134/2026/NĐ-CP.

Hệ thống có mục đích hỗ trợ tra cứu và nghiên cứu. Câu trả lời không thay thế việc kiểm tra văn bản pháp luật hoặc tư vấn pháp lý chuyên môn.

## 2. Mục tiêu (Objectives)

Project hướng đến các mục tiêu sau:

1. Xây dựng chatbot hỗ trợ tra cứu quyền tác giả đối với chương trình máy tính.
2. Áp dụng RAG để cung cấp context pháp lý cho mô hình ngôn ngữ.
3. So sánh Dense Retrieval, BM25 và Hybrid Retrieval.
4. So sánh context được truy hồi với thí nghiệm Long-Context.
5. Đánh giá khả năng truy xuất đúng Điều và Khoản liên quan.
6. Kiểm tra khả năng xử lý câu hỏi ngoài phạm vi.
7. Cung cấp citation cho căn cứ được sử dụng trong câu trả lời.

## 3. Kiến trúc hệ thống (System Architecture)

### Luồng xử lý chính

```text
Câu hỏi người dùng
        |
        v
Refusal / Input Handling
        |
        v
Hybrid Retrieval
   +----+----+
   |         |
   v         v
 Dense     BM25
   |         |
   +----+----+
        |
        v
       RRF
        |
        v
Context được truy hồi
        |
        v
Prompt Builder
        |
        v
Google Gemini
        |
        v
Structured JSON Response
        |
        v
Citation Resolver
        |
        v
RAGResponse
        |
        v
Web / CLI
```

### Các nhánh truy hồi

```text
Câu hỏi
   |
   +----> Dense Retrieval ----+
   |                          |
   +----> BM25 Retrieval -----+--> RRF --> Top-K Results
   |
   +----> Entity Retrieval ---+
```

Hybrid Retrieval hiện sử dụng ba nhánh Dense, Sparse và Entity. Các kết quả được hợp nhất bằng RRF với `RRF_K=15`.

## 4. Các thành phần chính (Features)

### Ingestion

Đọc văn bản luật, tách thành các đoạn theo Điều và Khoản, sau đó gắn metadata phục vụ truy hồi, kiểm tra hiệu lực và citation.

### Dense Retrieval

Sử dụng embedding để biểu diễn câu hỏi và đoạn luật dưới dạng vector. FAISS được dùng để tìm kiếm các vector liên quan.

### Sparse Retrieval

BM25 tìm các đoạn luật dựa trên mức độ khớp từ khóa và nội dung văn bản.

### Hybrid Retrieval

Kết hợp các kết quả truy hồi bằng Reciprocal Rank Fusion (RRF), nhằm sử dụng đồng thời thông tin ngữ nghĩa, từ khóa và số Điều/Khoản.

### Refusal Gate

Kiểm tra câu hỏi ngoài phạm vi, kết quả truy hồi không đủ phù hợp hoặc tỷ lệ dữ liệu gây nhiễu cao trước khi gọi mô hình sinh câu trả lời.

### LLM Generation

Gemini nhận system prompt, câu hỏi và context được truy hồi, sau đó trả về structured output để pipeline xử lý tiếp.

### Citation

Citation được xử lý sau khi mô hình trả kết quả để xác định các đoạn luật thực tế đã được sử dụng trong câu trả lời.

### Giao diện

Ứng dụng Streamlit cung cấp giao diện hỏi đáp trên web. CLI được dùng để chạy thử quy trình từ nạp dữ liệu đến trả lời.

## 5. Cấu trúc project (Project Structure)

```text
software-copyright-ip-rag/
|
+-- data/
|   +-- raw/                    Văn bản luật và metadata nguồn
|   +-- processed/              chunks và chỉ mục đã tạo
|   +-- evaluation/             Tập câu hỏi đánh giá
|
+-- ingestion/                 Đọc, tách và chuẩn hóa văn bản
|   +-- chunker.py
|   +-- metadata.py
|   +-- utils.py
|
+-- retrieval/                 Embedding, FAISS, BM25 và truy hồi
|   +-- retriever.py
|   +-- faiss_index.py
|   +-- bm25_index.py
|   +-- embedder.py
|
+-- generation/                Prompt, Gemini, refusal và citation
|   +-- llm.py
|   +-- prompt_builder.py
|   +-- refusal_gate.py
|   +-- citation_resolver.py
|
+-- evaluation/                Pipeline, thí nghiệm và metrics
|   +-- core/
|   +-- scripts/
|   +-- results/
|
+-- monitoring/                Theo dõi và kiểm tra hiệu lực văn bản
+-- webapp/                    Ứng dụng Streamlit
+-- tests/                     Bộ kiểm thử
+-- main.py                    Điểm vào CLI
+-- pipeline.py                RAGPipeline và answer_rag
+-- config.py                  Cấu hình dùng chung
+-- requirements.txt           Danh sách thư viện
+-- README.md                  Tài liệu dự án
```

## 6. Yêu cầu môi trường (Requirements)

- Python 3.11 trở lên được khuyến nghị.
- Môi trường ảo Python được khuyến nghị.
- Kết nối mạng để tải mô hình embedding khi cần.
- Khóa API Gemini nếu chạy các luồng cần sinh câu trả lời.
- Các thư viện được khai báo trong `requirements.txt`.

Các công nghệ chính gồm Python, Sentence Transformers, FAISS, BM25, Google Gemini, Streamlit, PyVI và pytest.

## 7. Cài đặt (Installation)

Từ thư mục gốc project, tạo môi trường ảo:

```bash
python -m venv .venv
```

Kích hoạt môi trường ảo theo hệ điều hành, sau đó cài dependencies:

```bash
python -m pip install -r requirements.txt
```

Trên Windows PowerShell, có thể kích hoạt bằng:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 8. Cấu hình (Configuration)

Hệ thống đọc biến môi trường từ file `.env` ở thư mục gốc hoặc từ môi trường chạy hiện tại.

Biến bắt buộc cho việc gọi Gemini:

```text
GEMINI_API_KEY
```

Không ghi giá trị khóa API trực tiếp vào README, mã nguồn hoặc repository. Không commit file `.env` chứa thông tin xác thực.

Các thông số retrieval, generation và đường dẫn dữ liệu được quản lý tập trung trong `config.py`, gồm mô hình embedding, mô hình Gemini, `TOP_K`, `RRF_K`, `MAX_SEQ_LENGTH` và các ngưỡng của Refusal Gate.

## 9. Chuẩn bị dữ liệu (Data Preparation)

Quy trình chuẩn bị dữ liệu:

```text
Văn bản pháp luật
        |
        v
Document Parsing
        |
        v
Chunking theo Điều / Khoản
        |
        v
Metadata
     +--+--+
     |     |
     v     v
 FAISS   BM25
```

Văn bản nguồn được đặt trong `data/raw/`. Dữ liệu xử lý và chỉ mục được lưu trong `data/processed/`. Khi thay đổi văn bản nguồn hoặc mô hình embedding, có thể cần tạo lại dữ liệu xử lý và chỉ mục bằng tùy chọn `--force`.

## 10. Chạy chatbot (Run Application)

### CLI

Chạy thử quy trình chatbot với các câu hỏi mẫu:

```bash
python main.py
```

Làm tươi dữ liệu xử lý và chỉ mục trước khi chạy:

```bash
python main.py --force
```

### Ứng dụng web

Khởi động Streamlit:

```bash
streamlit run webapp/app.py
```

Sau đó mở địa chỉ do Streamlit in ra trong terminal.

### Kiểm tra module hiệu lực

```bash
python -m monitoring.effective_checker
```

## 11. Chạy đánh giá (Run Evaluation)

Evaluation được điều phối bởi `evaluation/scripts/run_all.py`.

Chạy toàn bộ các experiment trên tập phát triển:

```bash
python evaluation/scripts/run_all.py --split dev --pipeline all
```

Chạy riêng Hybrid Retrieval:

```bash
python evaluation/scripts/run_all.py --split dev --pipeline hybrid
```

Tạo cấu trúc thư mục đánh giá mà không gọi Gemini:

```bash
python evaluation/scripts/run_all.py --split dev --dry-run
```

Một số tùy chọn thường dùng:

- `--limit N`: giới hạn số câu hỏi để chạy thử.
- `--disable-entity`: tắt nhánh Entity trong Hybrid Retrieval.
- `--semantic-only-gate`: tắt lớp từ khóa của Refusal Gate.

## 12. Các thí nghiệm (Evaluation Experiments)

Các experiment chính:

| Experiment | Mục đích |
| --- | --- |
| `dense-only` | Đánh giá Dense Retrieval bằng FAISS |
| `bm25-only` | Đánh giá Sparse Retrieval bằng BM25 |
| `hybrid` | Đánh giá Dense, BM25, Entity và RRF |
| `long-context` | So sánh với context dài theo pipeline tương ứng |

Luồng đánh giá tổng quát:

```text
Dataset
   |
   v
Experiment
   |
   v
Retrieval
   |
   v
Generation
   |
   v
Citation / Refusal
   |
   v
Metrics
   |
   v
Results
```

## 13. Dữ liệu đánh giá (Dataset)

Dữ liệu đánh giá nằm trong `data/evaluation/`, gồm tập phát triển và tập giữ lại.

Các trường dữ liệu được dùng tùy theo experiment có thể gồm:

- `id`: mã câu hỏi.
- `group`: nhóm câu hỏi.
- `scope`: phạm vi câu hỏi.
- `expected_behavior`: hành vi mong đợi.
- `question`: nội dung câu hỏi.
- `gold_ids`: mã đoạn luật tham chiếu khi có.
- `reference_answer`: câu trả lời tham chiếu khi có.

Dataset phục vụ evaluation, không phải dữ liệu đầu vào trực tiếp của chatbot trong thời gian chạy thông thường.

## 14. Chỉ số (Metrics)

Các nhóm chỉ số được sử dụng trong evaluation gồm:

- Recall@k ở cấp đoạn luật.
- Article Recall@k ở cấp Điều.
- Citation Precision, Citation Recall và Citation Exact Match.
- Các chỉ số refusal như TRR, FAR và FRR.
- Độ trễ và thông tin lỗi hoặc retry khi được pipeline ghi nhận.

Kết quả chi tiết phụ thuộc vào experiment, dataset, cấu hình và lần chạy cụ thể.

## 15. Kết quả (Results)

Kết quả evaluation được lưu riêng theo từng lần chạy trong:

```text
evaluation/results/
└── <timestamp>/
    ├── dense_only/
    ├── bm25_only/
    ├── hybrid/
    ├── long_context/
    ├── summary.json
    └── metadata.json
```

Các file kết quả có thể chứa thông tin về experiment, mô hình, cấu hình truy hồi, dataset, metrics và trạng thái thực thi. README không xem một lần chạy riêng lẻ là kết luận cho mọi dữ liệu.

## 16. Kiểm thử (Tests)

### Kiểm thử

Chạy toàn bộ test:

```bash
pytest tests/ -v
```

Có thể chạy riêng từng file:

```bash
pytest tests/test_unit.py -v
pytest tests/test_poc.py -v
```

Test tập trung vào các thành phần và hành vi chính của hệ thống.

## 17. Giới hạn (Limitations)

- Phạm vi trả lời phụ thuộc vào các văn bản được đưa vào corpus.
- Chất lượng câu trả lời phụ thuộc vào chất lượng chunking, retrieval, model embedding và Gemini.
- Gemini có thể gặp lỗi mạng, timeout, rate limit hoặc yêu cầu cấu hình API hợp lệ.
- Long-Context có thể làm tăng kích thước context và thời gian xử lý.
- Citation hỗ trợ xác định căn cứ từ context, không thay thế việc kiểm tra văn bản pháp luật gốc.
- Hệ thống không thay thế tư vấn pháp lý chuyên nghiệp.

## 18. Giấy phép / Tác giả (License / Author)

Repository hiện chưa cung cấp tệp giấy phép hoặc thông tin tác giả chính thức. Cần bổ sung các thông tin này trước khi phân phối project.
