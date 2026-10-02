# Báo Cáo Step 4 — Audit Reranker và Tính Nhất Quán Của Các Pipeline

Dựa trên quá trình kiểm tra mã nguồn hệ thống hiện tại, dưới đây là kết quả đối chiếu:

## 1. Trace Production Webapp (`webapp/app.py`)
Webapp sử dụng `RAGPipeline` làm bộ xử lý trung tâm.
- **Retrieval mode**: `hybrid`
- **Initial Retrieval K (Reranker Input)**: `15` (`config.RERANKER_INPUT_K`)
- **Reranker model**: `BAAI/bge-reranker-v2-m3`
- **Final K**: `5` (`config.TOP_K`)
- **Score threshold**: `0.22` (`config.MIN_SCORE_TIN_CAY`)
- **Distractor filtering**: Kiểm tra sau khi truy xuất (Refusal Gate), với tỷ lệ tối đa `0.6` (`config.MAX_DISTRACTOR_RATIO`).
- **Thứ tự**: Retrieve (K=15) → Rerank (xuống K=5) → Decide (Refusal Gate) → Prompt Build → LLM Generate.

## 2. Trace CLI (`main.py`)
- **Có reranker hay không**: KHÔNG. CLI đang gọi trực tiếp `retrieve_hybrid(top_k=config.TOP_K)` với K=5, không khởi tạo và không đi qua Reranker, dù trong `config.py` `ENABLE_RERANKER` đang = `True`.
- **Sự khác biệt**: Output của CLI (truy xuất K=5 trực tiếp qua RRF) sẽ khác hoàn toàn với Webapp (truy xuất K=15 rồi Rerank xuống K=5).
- **Mục đích**: CLI hiện tại có vẻ giống một tool debug hoặc một phiên bản cũ chưa được cập nhật kiến trúc `RAGPipeline` chung. 

## 3. Trace Evaluation (`run_all.py`)
- **Dense-only / BM25-only**: Giờ đã được tách ra chạy độc lập (qua `run_dense.py` và `run_BM25.py`), không đi qua Reranker.
- **Hybrid**: Chạy qua `run_RAG.py` với `RAGPipeline(mode="hybrid")`. Có nhận cờ `--enable-reranker` để mô phỏng Webapp.

**Bảng Đối Chiếu:**
| System | Entry point | Retriever | Initial K | Reranker | Final K | Production-equivalent? |
| ------ | ----------- | --------- | --------: | -------- | ------: | ---------------------- |
| Webapp | `app.py` | `RAGPipeline` | 15 | ✅ BGE-M3 | 5 | N/A (Ground truth) |
| CLI | `main.py` | `retrieve_hybrid()` | 5 | ❌ None | 5 | ❌ KHÔNG giống Webapp |
| Eval | `run_all.py` | `RAGPipeline` | 5 (nếu tắt) / 15 (nếu bật) | Tùy cờ CLI | 5 | ✅ CÓ THỂ (nếu truyền cờ) |

## 4. Kiểm tra Configuration Thực Tế (`config.py`)
- `ENABLE_RERANKER` = `True`
- `RERANKER_INPUT_K` = `15`
- `TOP_K` = `5`
- `RRF_K` = `15`
- `RERANKER_MODEL_NAME` = `"BAAI/bge-reranker-v2-m3"`
- `RERANKER_MAX_LENGTH` = `1024`
- `MIN_SCORE_TIN_CAY` = `0.22`

## 5. Kiểm tra Metadata
- **Đã có**: Trạng thái bật/tắt reranker (`enable_reranker`) đã được thêm vào mục `ablation_flags`.
- **Còn thiếu**: Tên mô hình reranker (`reranker_model_name`), Initial K (`RERANKER_INPUT_K`), và Final K (`TOP_K`) chưa được ghi nhận tường minh trong block gốc của metatdata (tuy `top_k` có trong config, nhưng không rõ context reranker).

## 6. Thiết Kế Controlled Experiment
Để chứng minh tác dụng thật sự của BAAI/bge-reranker-v2-m3, thử nghiệm cần chạy:
- **Baseline**: `python evaluation/scripts/run_all.py --pipeline hybrid` (Mặc định `--enable-reranker` là `False`).
- **Experiment**: `python evaluation/scripts/run_all.py --pipeline hybrid --enable-reranker`.

*(Ghi chú: Việc đánh giá diện rộng này sẽ gọi đến Gemini LLM để sinh kết quả, gây tốn thời gian. Cần một module đánh giá `retrieval` tách rời sử dụng `RAGPipeline` để đo Recall nhanh chóng hơn mà không phải gọi LLM).*

## 7. Kết Luận
- Có sự bất đồng bộ lớn giữa **Production (Webapp)** và **CLI (main.py)**: Webapp dùng Reranker, CLI không dùng.
- Thử nghiệm evaluation `run_all.py` đã được cập nhật để đo được cả hai trạng thái.

## 8. Quyết Định Sửa
**SHOULD FIX PRODUCTION/EVALUATION CONSISTENCY: YES**
- **Entry point cần thay đổi**: 
  1. Thay thế luồng truy xuất tĩnh trong `main.py` bằng việc gọi `RAGPipeline` tương tự như `app.py`. Điều này đảm bảo CLI phản ánh chính xác 100% logic của Webapp.
  2. Bổ sung các cấu hình phụ của Reranker (model name, input K) vào metadata log của `run_all.py`.
