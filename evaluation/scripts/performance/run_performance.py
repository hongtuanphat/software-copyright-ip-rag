import argparse
import json
from pathlib import Path
from collections import Counter

from evaluation.core.analysis import latency_summary, classify_errors


def evaluate_performance(generation_path: Path) -> dict[str, dict[str, float]] | None:
    """Read generation results and extract performance metrics."""
    if not generation_path.exists():
        return None
        
    records = []
    with generation_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            records.append(json.loads(line))
            
    if not records:
        return None

    # Tính toán tổng hợp độ trễ (latency) dựa trên core logic hiện có
    perf = latency_summary(records)
    errors = classify_errors(records)
    
    def _response(r): return r.get("response", r)
    
    retry_stats = {
        "observed_retry_count": sum(int(_response(r).get("retry_count", 0) or 0) for r in records),
        "records_with_retry": sum(int(_response(r).get("retry_count", 0) or 0) > 0 for r in records),
    }
    
    error_counts = dict(Counter(item["category"] for item in errors))
    
    return {
        "latency": perf,
        "reliability": {
            "retry_stats": retry_stats,
            "error_counts": error_counts
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate performance metrics from generation results.")
    parser.add_argument("--dataset", type=Path, help="Path to original dataset (unused).")
    parser.add_argument("--output", type=Path, required=True, help="Directory to save performance_metrics_report.json.")
    args = parser.parse_args()

    generation_path = args.output / "generation_results.jsonl"
    report_path = args.output / "performance_metrics_report.json"

    metrics = evaluate_performance(generation_path)
    if metrics:
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        print(f"Lưu báo cáo Performance tại {report_path}")
    else:
        print(f"Không tìm thấy hoặc không thể phân tích dữ liệu Performance tại {generation_path}")


if __name__ == "__main__":
    main()
