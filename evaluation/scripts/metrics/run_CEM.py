"""evaluation/scripts/metrics/run_CEM.py

Đánh giá Citation Exact Match (CEM), Citation Precision, và Citation Recall 
dựa trên gold_ids và các trích dẫn (citations) do hệ thống sinh ra trong kết quả thử nghiệm.
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
from evaluation.core.metrics import CitationMetricsReport, extract_article_level
from evaluation.core.utils import is_out_of_scope


def evaluate_cem(file_path: Path) -> dict:
    """Đọc file kết quả jsonl và tính toán các chỉ số Citation cho file đó."""
    if not file_path.exists():
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    report = CitationMetricsReport()
    success_count = 0
    error_count = 0

    for rec in records:
        req = rec.get("request", {})
        res = rec.get("response", {})
        
        status = res.get("status")
        if status == "error":
            error_count += 1
        else:
            success_count += 1

        gold_ids = req.get("gold_ids") or []
        out_of_scope = is_out_of_scope(req)
        
        if out_of_scope is None:
            continue
            
        is_in_scope = not out_of_scope
        
        pred_list = []
        if status != "error":
            cited_docs = res.get("cited_documents", [])
            for doc in cited_docs:
                if isinstance(doc, dict) and "provision_id" in doc:
                    pred_list.append(doc["provision_id"])
            
        is_in_scope = not out_of_scope
        
                
        pred_set = set(pred_list)



        if is_in_scope and gold_ids:
            gold_set = set(gold_ids)
            gold_art_set = extract_article_level(gold_set)
            pred_art_set = extract_article_level(pred_set)
            
            report.add_record(gold_set, pred_set, gold_art_set, pred_art_set)
            
    result = report.to_dict()
    total = len(records)
    result["total_records"] = total
    result["success_count"] = success_count
    result["error_count"] = error_count
    result["success_rate"] = round((success_count / total) * 100, 2) if total else 0.0
    result["failure_rate"] = round((error_count / total) * 100, 2) if total else 0.0
    return result

def main():
    parser = argparse.ArgumentParser(description="Chấm điểm Citation Exact Match (CEM) cho các hệ thống.")
    parser.add_argument("--date", type=str, default=None, help="Tên thư mục ngày chứa kết quả (vd: 11_09_2026_21_27_09)")
    args = parser.parse_args()

    results_dir = config.PROJECT_ROOT / "evaluation" / "results"
    
    if args.date:
        target_dir = results_dir / args.date
        if not target_dir.exists():
            print(f"[Lỗi] Không tìm thấy thư mục {target_dir}")
            return
    else:
        # Tự động tìm thư mục kết quả mới nhất
        subdirs = [d for d in results_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]
        if not subdirs:
            print("[Lỗi] Không tìm thấy thư mục kết quả nào trong evaluation/results/")
            return
        # Lấy thư mục có thời gian sửa đổi gần nhất
        target_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
        
    print(f"Đang đánh giá Citation Exact Match cho kết quả tại:\n{target_dir}\n")
    
    systems = {
        d.name: d / "generation_results.jsonl"
        for d in target_dir.iterdir() if d.is_dir()
    }
    
    print(f"{'Hệ Thống':<15} | {'Số Câu':<8} | {'Exact Match':<12} | {'Precision':<10} | {'Recall':<10} | {'Art. EM':<10} | {'Art. Prec':<10} | {'Art. Rec':<10} | {'Success Rate':<12}")
    print("-" * 130)
    
    final_report = {}
    
    for sys_name, file_path in systems.items():
        if not file_path.exists():
            continue
            
        metrics = evaluate_cem(file_path)
        if metrics:
            final_report[sys_name] = metrics
            print(f"{sys_name.upper():<15} | {metrics['eval_records']:<8} | {metrics['exact_match_rate']:>10.2f}% | {metrics['citation_precision']:>8.2f}% | {metrics['citation_recall']:>8.2f}% | {metrics['article_exact_match_rate']:>8.2f}% | {metrics['article_citation_precision']:>8.2f}% | {metrics['article_citation_recall']:>8.2f}% | {metrics['success_rate']:>11.2f}%")

    print("-" * 130)
    
    if final_report:
        report_path = target_dir / "CEM_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)
        print(f"\n-> Đã lưu báo cáo CEM chi tiết tại {report_path}")

if __name__ == "__main__":
    main()
