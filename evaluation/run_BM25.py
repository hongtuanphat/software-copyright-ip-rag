"""evaluation/run_BM25.py

Chạy thử nghiệm trên 100 câu hỏi (dev_set.json) chỉ sử dụng mô hình BM25 để retrieval.
Output được lưu vào evaluation/results/bm25_results.jsonl
Có hỗ trợ resume cho các câu đã thành công.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Nạp thư mục gốc vào sys.path để chạy trực tiếp từ bất kỳ đâu
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from ingestion.chunker import Provision
from retrieval.bm25_index import Bm25Index
from retrieval.retriever import retrieve_bm25

def load_processed_ids(output_path: Path) -> set[str]:
    """Đọc file jsonl và trả về danh sách các id đã xử lý thành công."""
    processed = set()
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        if record.get("status") == "success":
                            processed.add(record["id"])
                    except json.JSONDecodeError:
                        pass
    return processed

def run_bm25_experiment() -> None:
    dataset_path = config.DATA_DIR / "evaluation" / "dev_set.json"
    output_dir = Path(__file__).resolve().parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "bm25_results.jsonl"

    if not dataset_path.exists():
        print(f"[Lỗi] Không tìm thấy tập dữ liệu tại: {dataset_path}")
        return

    # Tải dữ liệu chunks và khởi tạo BM25
    print("Đang nạp dữ liệu chunks và khởi tạo BM25 index...")
    provisions: list[Provision] = []
    with open(config.CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                provisions.append(Provision(**json.loads(line)))
                
    texts = [p.text for p in provisions]
    pids = [p.provision_id for p in provisions]
    bm25_index = Bm25Index(texts, pids)

    # Đọc câu hỏi
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    questions = data if isinstance(data, list) else data.get("questions", [])

    processed_ids = load_processed_ids(output_path)
    
    print(f"Bắt đầu chạy thử nghiệm BM25 cho {len(questions)} câu hỏi...")
    if processed_ids:
        print(f"-> Chế độ Resume: Bỏ qua {len(processed_ids)} câu đã thành công.")

    with open(output_path, "a", encoding="utf-8") as out_f:
        for i, item in enumerate(questions, 1):
            q_id = item.get("id", str(i))
            q_text = item.get("question", "")
            q_group = item.get("group", "unknown")
            expected_behavior = item.get("expected_behavior", "answer")
            gold_ids = item.get("gold_ids", [])

            if q_id in processed_ids:
                print(f"[{i}/{len(questions)}] Câu {q_id}: Đã có kết quả thành công từ trước, bỏ qua.")
                continue

            print(f"[{i}/{len(questions)}] Đang truy hồi BM25 cho câu {q_id}...")
            
            start_time = time.perf_counter()
            try:
                hits = retrieve_bm25(q_text, provisions, bm25_index, top_k=config.TOP_K)
                retrieved_ids = [h.provision.provision_id for h in hits]
                latency_ms = (time.perf_counter() - start_time) * 1000.0

                record = {
                    "id": q_id,
                    "question": q_text,
                    "group": q_group,
                    "expected_behavior": expected_behavior,
                    "gold_ids": gold_ids,
                    "answer": None,
                    "retrieved_ids": retrieved_ids,
                    "citations": [],
                    "refused": False,
                    "latency_ms": round(latency_ms, 2),
                    "status": "success"
                }
            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                print(f"  -> [Lỗi] {str(e)}")
                record = {
                    "id": q_id,
                    "question": q_text,
                    "group": q_group,
                    "expected_behavior": expected_behavior,
                    "gold_ids": gold_ids,
                    "answer": None,
                    "retrieved_ids": [],
                    "citations": [],
                    "refused": False,
                    "latency_ms": round(latency_ms, 2),
                    "status": "error",
                    "error": str(e)
                }

            # Ghi ngay xuống file
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()

    print(f"\nHoàn thành chạy BM25. Kết quả được lưu tại: {output_path}")

if __name__ == "__main__":
    run_bm25_experiment()
