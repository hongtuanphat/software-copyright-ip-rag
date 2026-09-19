"""evaluation/scripts/run_refusal_metrics.py

Đánh giá TP, FP, TN, FN và TRR, FAR, FRR dựa trên response.refused và expected_behavior.
"""
import argparse
import json
import sys
from pathlib import Path

# Đảm bảo chạy từ thư mục gốc
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.core.runner import setup_encoding
setup_encoding()

import config
from evaluation.core.metrics import RefusalConfusionMatrix, build_confusion_matrix

def calculate_metrics(file_path: Path) -> dict:
    if not file_path.exists():
        print(f"File không tồn tại: {file_path}")
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    gold_list = []
    pred_list = []
    skipped_error = 0

    print(f"\nĐang tính Metrics cho file: {file_path.name} ({len(records)} records)")
    for i, rec in enumerate(records, 1):
        req = rec.get("request", {})
        res = rec.get("response", {})

        # Bỏ qua bản ghi lỗi — không tính API error thành refusal
        if res.get("status") == "error":
            skipped_error += 1
            continue

        expected = str(req.get("expected_behavior", "answer")).lower()

        # Sử dụng field `response.refused` (bool)
        refused_val = res.get("refused")
        if refused_val is None:
            print(f"  [Cảnh báo] Dòng {i} (ID: {req.get('id')}) thiếu 'refused'. Bỏ qua.")
            continue

        gold_list.append(expected == "refuse")
        pred_list.append(bool(refused_val))

    if skipped_error:
        print(f"  [Info] Đã bỏ qua {skipped_error} bản ghi status='error'.")

    if not gold_list:
        print(f"Không có dữ liệu hợp lệ nào để chấm điểm trong {file_path.name}")
        return {}

    cm = build_confusion_matrix(gold_list, pred_list)
    return cm.to_dict()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None, help="Tên thư mục kết quả (vd: 11_09_2026_21_27_09)")
    args = parser.parse_args()
    
    results_base = config.PROJECT_ROOT / "evaluation" / "results"
    
    if args.date:
        results_dir = results_base / args.date
        if not results_dir.exists():
            print(f"[Lỗi] Thư mục không tồn tại: {results_dir}")
            return
    else:
        subdirs = [d for d in results_base.iterdir() if d.is_dir() and d.name != "__pycache__"]
        if not subdirs:
            print("[Lỗi] Không tìm thấy thư mục kết quả nào trong evaluation/results/")
            return
        results_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
        print(f"[Auto] Đã tự động chọn thư mục kết quả mới nhất: {results_dir.name}")
    
    final_report = {}
    systems = set()
    for f in results_dir.glob("*.json*"):
        if "report" not in f.name.lower():
            sys_name = f.stem  # lấy toàn bộ system, vd: "rag", "bm25", "gemini"
            systems.add(sys_name)
    
    for sys_name in systems:
        file_path = None
        for f in results_dir.glob(f"{sys_name}.json*"):
            if "report" not in f.name.lower():
                file_path = f
                break
            
        if file_path and file_path.exists():
            metrics = calculate_metrics(file_path)
            if metrics:
                final_report[sys_name] = metrics
                print(f"\n--- Báo cáo {sys_name.upper()} ---")
                print(f"TRR (Từ chối đúng): {metrics['trr']}%")
                print(f"FAR (Chấp nhận nhầm): {metrics['far']}%")
                print(f"FRR (Từ chối nhầm): {metrics['frr']}%")
                print(f"Tổng: {metrics['total']} câu (TR: {metrics['true_refusal']}, FA: {metrics['false_accept']}, TA: {metrics['true_accept']}, FR: {metrics['false_refusal']})\n")

    if final_report:
        report_path = results_dir / "refusal_metrics_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)
        print(f"Đã lưu báo cáo tổng hợp tại {report_path}")

if __name__ == "__main__":
    main()
