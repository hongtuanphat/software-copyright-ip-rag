"""evaluation/scripts/metrics/run_refusal_metrics.py

Đánh giá TP, FP, TN, FN và TRR, FAR, FRR dựa trên response.refused và expected_behavior.
"""
import argparse
import json
import sys
from pathlib import Path

# Đảm bảo chạy từ thư mục gốc
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.core.runner import setup_encoding
setup_encoding()

import config
from evaluation.core.metrics import RefusalConfusionMatrix, build_confusion_matrix
from evaluation.core.utils import is_out_of_scope, get_refused

def calculate_metrics(file_path: Path) -> dict:
    if not file_path.exists():
        print(f"File không tồn tại: {file_path}")
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    gold_list = []
    pred_list = []
    success_count = 0
    error_count = 0

    print(f"\nĐang tính Metrics cho file: {file_path.name} ({len(records)} records)")
    for i, rec in enumerate(records, 1):
        req = rec.get("request", {})
        res = rec.get("response", {})

        status = res.get("status")
        if status == "error":
            error_count += 1
            # Không tính API error vào bộ đếm Confusion Matrix, 
            # nhưng vẫn đếm vào error_count để báo cáo failure rate.
            continue
        else:
            success_count += 1

        out_of_scope = is_out_of_scope(req)
        refused_val = get_refused(res)

        if out_of_scope is None or refused_val is None:
            print(f"  [Cảnh báo] Dòng {i} (ID: {req.get('id')}) dữ liệu không hợp lệ. Bỏ qua.")
            continue

        gold_list.append(out_of_scope)
        pred_list.append(refused_val)

    if error_count:
        print(f"  [Info] Hệ thống gặp {error_count} lỗi API (chiếm {round(error_count/len(records)*100, 2)}%).")

    if not gold_list:
        print(f"Không có dữ liệu hợp lệ nào để chấm điểm trong {file_path.name}")
        return {}

    cm = build_confusion_matrix(gold_list, pred_list)
    result = cm.to_dict()
    total = len(records)
    result["total_records"] = total
    result["success_count"] = success_count
    result["error_count"] = error_count
    result["success_rate"] = round((success_count / total) * 100, 2) if total else 0.0
    result["failure_rate"] = round((error_count / total) * 100, 2) if total else 0.0
    return result

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
    systems = [d.name for d in results_dir.iterdir() if d.is_dir()]
    
    for sys_name in systems:
        file_path = results_dir / sys_name / "generation_results.jsonl"
        if file_path.exists():
            metrics = calculate_metrics(file_path)
            if metrics:
                final_report[sys_name] = metrics
                print(f"\n--- Báo cáo {sys_name.upper()} ---")
                print(f"Success Rate: {metrics.get('success_rate', 0)}% ({metrics.get('success_count', 0)}/{metrics.get('total_records', 0)}) | Failure Rate: {metrics.get('failure_rate', 0)}%")
                print(f"TRR (Từ chối đúng): {metrics['trr']}%")
                print(f"FAR (Chấp nhận nhầm): {metrics['far']}%")
                print(f"FRR (Từ chối nhầm): {metrics['frr']}%")
                print(f"Tổng Refusal Eval: {metrics['total']} câu (TR: {metrics['true_refusal']}, FA: {metrics['false_accept']}, TA: {metrics['true_accept']}, FR: {metrics['false_refusal']})\n")

    if final_report:
        report_path = results_dir / "refusal_metrics_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)
        print(f"Đã lưu báo cáo tổng hợp tại {report_path}")

if __name__ == "__main__":
    main()
