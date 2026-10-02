# BƯỚC 6: CHẠY LẠI EVALUATION PIPELINE DUY NHẤT

## 1. Mục tiêu
Tự động hóa toàn bộ quy trình chạy đánh giá, không phải chạy các scripts thủ công rải rác. Đảm bảo tính lưu vết (Versioning) của thí nghiệm khoa học.

## 2. Vấn đề hiện tại (Theo bug.txt)
- Các file kết quả bị commit nhầm lên Git, gây hiểu lầm cho đồng đội. Không ghi lại tên Model và cấu hình đã dùng.
- Quy trình đánh giá chưa được tự động hóa hoàn toàn, dẫn đến việc chạy thủ công mất nhiều thời gian và dễ mắc lỗi.


## 3. Kế hoạch hành động chi tiết
- **Viết Master Orchestrator (`run_all.py`):**
  - Gọi tuần tự các hàm/luồng: `Data Loading -> Retrieval Evaluation -> LLM Generation -> Citation Parsing -> Metric Calculation`.
  - Kết thúc quy trình, tạo ra một thư mục `evaluation/results/{timestamp}/`.
- **Lưu trữ Metadata:**
  - Tạo một file `metadata.json` trong mỗi thư mục kết quả để lưu trữ thông tin về thí nghiệm.
- Trong thư mục kết quả
├── __init__.py
│
├── core/
│   ├── __init__.py
│   ├── dataset.py
│   ├── metrics.py
│   └── runner.py
│
├── results/
│   ├── .gitkeep
│   │
│   └── <timestamp>/
│       ├── metadata.json - "run_id", "commit_hash", "date","top_k", "rrf_k", "min_dense_score", "max_distractor_ratio", "embedder_model_name", "llm_model_name", "vector_dim", "dataset","num_questions"
│       ├── retrieval/
│       │   ├── dense_only/
│       │   │   └── metrics.json
│       │   ├── bm25_only/
│       │   │   └── metrics.json
│       │   └── hybrid/
│       │       └── metrics.json
│       │
│       ├── generation/
│       │   ├── gemini_no_rag/
│       │   │   └── metrics.json
│       │   └── hybrid/
│       │       └── metrics.json
│       │
│       ├── performance/
│       │   ├── long_context/
│       │   │   └── metrics.json
│       │   └── hybrid/
│       │       └── metrics.json
│       │
│       └── summary.json
│
└── scripts/
    │
    ├── run_all.py
    │
    ├── retrieval/
    │   └── run_recall.py
    │
    ├── generation/
    │   ├── run_CEM.py
    │   └── run_refusal_metrics.py
    │
    ├── performance/
    │   └── run_performance.py
    │
    ├── pipelines/
    │   ├── run_RAG.py
    │   ├── run_BM25.py
    │   ├── run_gemini.py
    │   └── run_long_context.py
    │
    └── utils/
        └── split_dataset.py
- **Cập nhật `.gitignore`:**
  - Thêm dòng `evaluation/results/*` vào gitignore để đảm bảo các file kết quả chạy cục bộ không bị push lên repository gây nhiễu, tuy nhiên vẫn cần lưu trữ folder đó dưới local.

## 4. Nghiệm thu
- Kiểm tra trong `evaluation/results/` phải mọc ra thư mục mới chứa đầy đủ số liệu và metadata -> PASS.
- CHẠY 1 run_all.py kiểm tra đảm bảo eval đạt
