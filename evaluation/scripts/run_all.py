"""Single versioned orchestrator for retrieval and generation evaluation."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from evaluation.core.runner import setup_encoding
from evaluation.core.analysis import analyze_records

setup_encoding()


def _commit_hash() -> str:
    """Lấy git commit hash ngắn (7 ký tự). Trả về 'UNKNOWN' nếu không có git."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode().strip()
    except Exception:  # noqa: BLE001
        return "UNKNOWN"


def _vector_dim() -> int | None:
    try:
        import faiss
        return int(faiss.read_index(str(config.FAISS_INDEX_PATH)).d)
    except Exception:
        return None


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _execute_pipeline(name: str, generation_path: Path, dataset: Path, limit: int | None, args: argparse.Namespace) -> None:
    """Chạy một pipeline cụ thể."""
    if name == "dense_only":
        from evaluation.scripts.pipelines.run_dense import run_dense_experiment
        run_dense_experiment(dataset_path=dataset, output_path=generation_path, limit=limit)
    elif name == "bm25_only":
        from evaluation.scripts.pipelines.run_BM25 import run_bm25_experiment
        run_bm25_experiment(dataset_path=dataset, output_path=generation_path, limit=limit)
    elif name == "long_context":
        from evaluation.scripts.pipelines.run_long_context import run_long_context_experiment
        run_long_context_experiment(dataset_path=dataset, output_path=generation_path, limit=limit, delay_seconds=75.0)
    elif name == "hybrid":
        from evaluation.scripts.pipelines.run_RAG import run_hybrid_experiment
        run_hybrid_experiment(
            dataset_path=dataset,
            output_path=generation_path,
            limit=limit,
            disable_entity=args.disable_entity,
            semantic_only_gate=args.semantic_only_gate,
        )


def _evaluate_retrieval(generation_path: Path) -> dict[str, Any]:
    from evaluation.core.analysis import analyze_records
    records = [json.loads(line) for line in generation_path.read_text(encoding="utf-8").splitlines() if line]
    return analyze_records(records)


def _evaluate_generation(generation_path: Path) -> dict[str, Any]:
    from evaluation.scripts.metrics.run_CEM import evaluate_cem
    from evaluation.scripts.metrics.run_refusal_metrics import calculate_metrics
    
    metrics: dict[str, Any] = {}
    citation = evaluate_cem(generation_path)
    refusal = calculate_metrics(generation_path)
    if citation:
        metrics["citation"] = citation
    if refusal:
        metrics["refusal"] = refusal
    return metrics


def _evaluate_performance(generation_path: Path, ret_metrics: dict[str, Any] = None) -> dict[str, Any]:
    if ret_metrics:
        return {
            "latency": ret_metrics.get("latency", {}),
            "reliability": {
                "retry_stats": ret_metrics.get("retry", {}),
                "error_counts": ret_metrics.get("error_counts", {})
            }
        }
    
    from evaluation.scripts.performance.run_performance import evaluate_performance
    perf = evaluate_performance(generation_path)
    return perf if perf else {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy evaluation pipeline có version và metadata.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--split", choices=["dev", "heldout"], default="dev")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ tạo cấu trúc và metadata, không gọi Gemini.")
    parser.add_argument("--pipeline", choices=["all", "dense-only", "bm25-only", "long-context", "hybrid"], default="all", help="Chỉ chạy 1 baseline cụ thể hoặc chạy tất cả.")
    parser.add_argument("--disable-entity", action="store_true", help="Tắt nhánh Entity trong Hybrid RRF.")
    parser.add_argument("--semantic-only-gate", action="store_true", help="Tắt keyword layer để chạy ablation semantic-only.")
    parser.add_argument("--run-dir", type=str, default=None, help="Đường dẫn thư mục kết quả có sẵn để chạy bổ sung (ví dụ: evaluation/results/2026-10-01_21-41-47)")
    args = parser.parse_args()

    dataset = ROOT / "data" / "evaluation" / f"{args.split}_set.json"
    if not dataset.exists():
        raise FileNotFoundError(f"Không tìm thấy dataset: {dataset}")

    if args.run_dir:
        run_dir = Path(args.run_dir)
        if not run_dir.is_absolute():
            run_dir = ROOT / run_dir
        if not run_dir.exists():
            raise FileNotFoundError(f"Không tìm thấy thư mục: {run_dir}")
        timestamp = run_dir.name
    else:
        timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = ROOT / "evaluation" / "results" / timestamp
        run_dir.mkdir(parents=True, exist_ok=False)
    
    # Định nghĩa các thư mục hệ thống
    systems = {
        "dense_only": run_dir / "dense_only",
        "bm25_only": run_dir / "bm25_only",
        "long_context": run_dir / "long_context",
        "hybrid": run_dir / "hybrid",
    }
    for directory in systems.values():
        directory.mkdir(parents=True, exist_ok=True)

    questions = json.loads(dataset.read_text(encoding="utf-8"))
    metadata = {
        "run_id": timestamp,
        "commit_hash": _commit_hash(),
        "date": datetime.now(timezone.utc).isoformat(),
        "embedder_model_name": config.EMBEDDING_MODEL_NAME,
        "llm_model_name": config.GEMINI_MODEL_NAME,
        "vector_dim": _vector_dim(),
        "dataset": str(dataset.relative_to(ROOT)).replace("\\", "/"),
        "dataset_split": args.split,
        "num_questions": len(questions) if args.limit is None else min(args.limit, len(questions)),
        "baseline_mode": args.pipeline,
        "ablation_flags": {
            "disable_entity": args.disable_entity,
            "semantic_only_gate": args.semantic_only_gate,
        },
        "config": {
        "top_k": config.TOP_K,
        "rrf_k": config.RRF_K,
        "min_dense_score": config.MIN_SCORE_TIN_CAY,
        "max_distractor_ratio": config.MAX_DISTRACTOR_RATIO,
        },
    }
    _write_json(run_dir / "metadata.json", metadata)

    if args.dry_run:
        for name, directory in systems.items():
            _write_json(directory / "metrics.json", {"status": "not_run", "reason": "dry-run"})
        _write_json(run_dir / "summary.json", {"status": "not_run"})
        print(f"Dry-run evaluation structure created at {run_dir}")
        return

    all_runs = ["dense_only", "bm25_only", "long_context", "hybrid"]

    runs = []
    for run_name in all_runs:
        if args.pipeline == "all" or args.pipeline.replace("-", "_") == run_name:
            runs.append(run_name)

    summary_path = run_dir / "summary.json"
    if summary_path.exists() and args.run_dir:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["metadata"] = metadata
    else:
        summary: dict[str, Any] = {
            "metadata": metadata, 
            "retrieval": {}, 
            "generation": {}, 
            "performance": {}
        }
    
    for name in runs:
        exec_dir = systems[name]
        generation_path = exec_dir / "generation_results.jsonl"
        
        # 1. Chạy Pipeline
        _execute_pipeline(name, generation_path, dataset, args.limit, args)
        
        # 2. Trích xuất kết quả truy hồi (nếu có)
        if name not in ("long_context",):
            records = [json.loads(line) for line in generation_path.read_text(encoding="utf-8").splitlines() if line]
            retrieval_data = [{"id": r["request"]["id"], "retrieved_ids": r["response"].get("retrieved_ids", [])} for r in records]
            _write_json(exec_dir / "retrieval_results.json", retrieval_data)
                
        # 3. Tính toán các chỉ số dựa trên phạm vi
        system_metrics: dict[str, Any] = {}
        
        if name in ("dense_only", "bm25_only"):
            ret_metrics = _evaluate_retrieval(generation_path)
            gen_metrics = _evaluate_generation(generation_path)
            perf_metrics = _evaluate_performance(generation_path, ret_metrics)

            system_metrics["retrieval"] = ret_metrics
            system_metrics["generation"] = gen_metrics
            system_metrics["performance"] = perf_metrics

            summary["retrieval"][name] = ret_metrics
            summary["generation"][name] = gen_metrics
            summary["performance"][name] = perf_metrics
            
        elif name == "long_context":
            perf_metrics = _evaluate_performance(generation_path)
            system_metrics.update(perf_metrics)
            summary["performance"][name] = perf_metrics
            
        elif name == "hybrid":
            ret_metrics = _evaluate_retrieval(generation_path)
            gen_metrics = _evaluate_generation(generation_path)
            perf_metrics = _evaluate_performance(generation_path, ret_metrics)
            
            system_metrics["retrieval"] = ret_metrics
            system_metrics["generation"] = gen_metrics
            system_metrics["performance"] = perf_metrics
            
            summary["retrieval"]["hybrid"] = ret_metrics
            summary["generation"]["hybrid"] = gen_metrics
            summary["performance"]["hybrid"] = perf_metrics

        if system_metrics:
            _write_json(exec_dir / "metrics.json", system_metrics)

    _write_json(run_dir / "summary.json", summary)
    
    # 4. Tạo báo cáo final_metrics_report.json (bao gồm phân rã theo nhóm và Bootstrap CI)
    final_report = {
        "metadata": summary["metadata"],
        "retrieval": summary.get("retrieval", {}),
        "generation": summary.get("generation", {}),
    }
    
    hybrid_gen_path = systems.get("hybrid", run_dir) / "generation_results.jsonl"
    if hybrid_gen_path.exists():
        records = [json.loads(line) for line in hybrid_gen_path.read_text(encoding="utf-8").splitlines() if line]
        analysis_result = analyze_records(records)
        final_report["group_breakdown"] = analysis_result
        
        print("\n" + "="*80)
        print("FINAL METRICS REPORT (GROUP BREAKDOWN & BOOTSTRAP CI)")
        print("="*80)
        
        print("\n[RETRIEVAL - NHÓM 1, 2, 3]")
        for group, metrics in analysis_result.get("group_retrieval", {}).items():
            print(f"\n{group} (n={metrics.get('sample_size', 0)}):")
            for k in [1, 3, 5, 10]:
                cr = metrics.get(f"clause_recall@{k}")
                if cr:
                    pe = cr.get('point_estimate')
                    cil = cr.get('ci_lower')
                    ciu = cr.get('ci_upper')
                    pe_val = pe if pe is not None else 0
                    cil_val = cil if cil is not None else 0
                    ciu_val = ciu if ciu is not None else 0
                    print(f"  Clause Recall@{k}: {pe_val:.2%} (95% CI: [{cil_val:.2%}, {ciu_val:.2%}])")

        print("\n[REFUSAL - NHÓM 4, 5]")
        for group, metrics in analysis_result.get("group_refusal", {}).items():
            print(f"\n{group} (n={metrics.get('sample_size', 0)}):")
            trr = metrics.get('trr')
            far = metrics.get('far')
            trr_val = trr if trr is not None else 0
            far_val = far if far is not None else 0
            print(f"  True Refusal Rate (TRR): {trr_val:.2f}%")
            print(f"  False Accept Rate (FAR): {far_val:.2f}%")
            
    _write_json(run_dir / "final_metrics_report.json", final_report)
    print(f"\nEvaluation completed: {run_dir}")
    print(f"Báo cáo chi tiết đã được lưu tại: {run_dir / 'final_metrics_report.json'}")


if __name__ == "__main__":
    main()
