"""evaluation/scripts/run_CEM.py

Đánh giá Citation Exact Match (CEM), Citation Precision, và Citation Recall 
dựa trên gold_ids và các trích dẫn (citations) do hệ thống sinh ra trong kết quả thử nghiệm.
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
from evaluation.core.metrics import CitationMetricsReport, extract_citations_from_text, extract_article_level

def evaluate_cem(file_path: Path) -> dict:
    """Đọc file kết quả jsonl và tính toán các chỉ số Citation cho file đó."""
    if not file_path.exists():
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    report = CitationMetricsReport()

    for rec in records:
        req = rec.get("request", {})
        res = rec.get("response", {})
        gold_ids = req.get("gold_ids", [])

        if res.get("status") == "error":
            continue

        if not gold_ids:
            continue
            
        gold_set = set(gold_ids)
        gold_art_set = extract_article_level(gold_set)
        
        # 1. Trích xuất citations từ kết quả trả về
        citations = res.get("citations", [])
        pred_set = set()
        
        if isinstance(citations, list) and citations:
            for c in citations:
                if isinstance(c, dict) and "provision_id" in c:
                    pred_set.add(c["provision_id"])
                elif isinstance(c, str):
                    # Đôi khi citation có thể là dạng text [Art12] nên parse tiếp
                    pred_set.update(extract_citations_from_text(c))
        
        # Removed fallback parse of answer text to prevent inflating CEM metric
            
        pred_art_set = extract_article_level(pred_set)
        
        report.add_record(gold_set, pred_set, gold_art_set, pred_art_set)

    return report.to_dict()

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
    
    # Các file cần quét (giống run_all.py đã tạo ra)
    systems = ["gemini", "bm25", "rag"]
    
    print(f"{'Hệ Thống':<15} | {'Số Câu':<8} | {'Exact Match':<12} | {'Precision':<10} | {'Recall':<10} | {'Art. EM':<10} | {'Art. Prec':<10} | {'Art. Rec':<10}")
    print("-" * 105)
    
    final_report = {}
    
    for sys_name in systems:
        file_path = None
        for f in target_dir.glob(f"{sys_name}.json*"):
            file_path = f
            break
            
        if not file_path or not file_path.exists():
            continue
            
        metrics = evaluate_cem(file_path)
        if metrics:
            final_report[sys_name] = metrics
            print(f"{sys_name.upper():<15} | {metrics['eval_records']:<8} | {metrics['exact_match_rate']:>10.2f}% | {metrics['citation_precision']:>8.2f}% | {metrics['citation_recall']:>8.2f}% | {metrics['article_exact_match_rate']:>8.2f}% | {metrics['article_citation_precision']:>8.2f}% | {metrics['article_citation_recall']:>8.2f}%")

    print("-" * 105)
    
    if final_report:
        report_path = target_dir / "CEM_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)
        print(f"\n-> Đã lưu báo cáo CEM chi tiết tại {report_path}")

if __name__ == "__main__":
    main()