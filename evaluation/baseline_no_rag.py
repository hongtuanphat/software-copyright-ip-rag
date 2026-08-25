"""evaluation/baseline_no_rag.py

Script chạy thử nghiệm Zero-shot No-RAG:
Hỏi trực tiếp mô hình Gemini với 100 câu trong dev_set.json mà không kèm ngữ cảnh luật.
Kết quả được lưu vào evaluation/baseline_results.json để đối chứng với kết quả chạy RAG.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import config
from generation.llm import generate_no_rag


def run_baseline_no_rag(
    dataset_path: Path | None = None,
    output_path: Path | None = None,
) -> None:
    """Chạy lần lượt 100 câu hỏi và lưu lại câu trả lời trực tiếp từ Gemini."""
    if dataset_path is None:
        dataset_path = config.DATA_DIR / "dev_set.json"
    if output_path is None:
        output_path = Path(__file__).resolve().parent / "baseline_results.json"

    if not dataset_path.exists():
        print(f"[Lỗi] Không tìm thấy file bộ câu hỏi tại: {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = data.get("questions", [])
    print(f"Bắt đầu chạy đối chứng No-RAG cho {len(questions)} câu hỏi...")

    results = []
    for i, item in enumerate(questions, 1):
        q_id = item.get("id", str(i))
        q_text = item.get("question", "")
        q_type = item.get("type", "unknown")

        print(f"[{i}/{len(questions)}] Đang gửi câu hỏi {q_id}: {q_text[:60]}...")
        t0 = time.time()
        answer = generate_no_rag(q_text)
        elapsed = time.time() - t0

        results.append({
            "id": q_id,
            "type": q_type,
            "question": q_text,
            "ground_truth_provisions": item.get("ground_truth_provisions", []),
            "baseline_answer": answer,
            "execution_time_seconds": round(elapsed, 3),
        })
        time.sleep(0.5)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Hoàn thành đối chứng No-RAG. Đã lưu kết quả tại: {output_path}")


if __name__ == "__main__":
    run_baseline_no_rag()
