# Chatbot RAG Tra Cứu Quyền Tác Giả Chương Trình Máy Tính (Luật SHTT)

Hệ thống Chatbot RAG (Retrieval-Augmented Generation) tra cứu pháp luật về bảo hộ quyền tác giả đối với chương trình máy tính theo Văn bản hợp nhất số 67/VBHN-VPQH (ngày 23/03/2026).

---

## Cài Đặt Môi Trường

Khuyến nghị sử dụng Python 3.11+.

```bash
pip install -r requirements.txt
```

---

## Cấu Hình Biến Môi Trường (.env)

Tạo file `.env` tại thư mục gốc và điền Gemini API key:

```env
GEMINI_API_KEY=your_api_key_here
```

---

## Hướng Dẫn Vận Hành PoC

### 1. Chạy thử nghiệm CLI (5 Nhóm câu hỏi mẫu)
```bash
python main.py
```
Lệnh trên thực hiện quy trình end-to-end: nạp dữ liệu thô, tách khối (chunking), đánh chỉ mục FAISS/BM25, thực thi truy hồi (retrieval), đánh giá từ chối (refusal gate), và sinh câu trả lời kèm trích dẫn pháp lý.

### 2. Chạy bộ kiểm thử tự động
```bash
pytest tests/ -v
```

### 3. Chạy kiểm tra module giám sát hiệu lực (Mock Data)
```bash
python -m monitoring.effective_checker
```

---

## Cấu Trúc Dự Án

```text
project/
├── config.py                 # Cấu hình hằng số hệ thống
├── main.py                   # Điểm vào CLI thử nghiệm
├── pipeline.py               # Backend Service API (RAGPipeline, answer_rag)
├── requirements.txt          # Thư viện phụ thuộc
├── data/
│   ├── raw/                  # Văn bản thô (67-VBHN-VPQH.txt & metadata)
│   └── processed/            # Dữ liệu xử lý (.jsonl, .index)
├── ingestion/                # Tách khối (chunker.py) & gán metadata (metadata.py)
├── retrieval/                # Embedding, FAISS index, BM25 index & Retriever
├── generation/               # Refusal Gate, Prompt Builder, LLM Client & Citation
├── monitoring/               # Module cào dữ liệu (crawler.py) & kiểm tra hiệu lực (effective_checker.py)
├── evaluation/               # Đo lường chỉ số (metrics.py: TRR, FRR, FAR, Recall@k)
├── webapp/                   # Giao diện Webbot Streamlit (app.py)
└── tests/                    # Unit test suite (test_poc.py)
```
