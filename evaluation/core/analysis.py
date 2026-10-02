"""Evidence-based group, confidence, error, and latency analysis."""
from __future__ import annotations

import re
from collections import Counter
from statistics import median
from typing import Any, Iterable

import numpy as np
from scipy.stats import bootstrap

from evaluation.core.metrics import (
    build_confusion_matrix,
    hierarchical_article_recall_at_k,
    recall_at_k,
)
from evaluation.core.utils import is_out_of_scope, get_refused


def bootstrap_ci(values: Iterable[float], n_resamples: int = 1000, confidence_level: float = 0.95) -> dict[str, Any]:
    data = np.asarray(list(values), dtype=float)
    if data.size == 0:
        return {
            "metric": None,
            "point_estimate": None,
            "ci_lower": None,
            "ci_upper": None,
            "confidence_level": confidence_level,
            "n_resamples": n_resamples,
            "sample_size": 0,
        }
    if data.size == 1:
        low = high = float(data[0])
    else:
        result = bootstrap(
            (data,),
            np.mean,
            n_resamples=n_resamples,
            confidence_level=confidence_level,
            method="percentile",
            rng=np.random.default_rng(0),
        )
        low, high = float(result.confidence_interval.low), float(result.confidence_interval.high)
    return {
        "metric": None,
        "point_estimate": float(np.mean(data)),
        "ci_lower": low,
        "ci_upper": high,
        "confidence_level": confidence_level,
        "n_resamples": n_resamples,
        "sample_size": int(data.size),
    }


def _group_name(record: dict[str, Any]) -> str:
    return str(record.get("request", {}).get("group", record.get("group", "unknown")))


def _request(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("request", record)


def _response(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("response", record)



def group_retrieval(records: list[dict[str, Any]], k_values: tuple[int, ...] = (1, 3, 5, 10)) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for group in ("Nhóm 1", "Nhóm 2", "Nhóm 3"):
        group_records = [r for r in records if _group_name(r) == group and is_out_of_scope(_request(r)) is False and _response(r).get("status") != "error"]
        metrics: dict[str, Any] = {"sample_size": len(group_records)}
        for k in k_values:
            clause = [recall_at_k(_request(r).get("gold_ids", []), _response(r).get("retrieved_ids", []), k) for r in group_records]
            article = [hierarchical_article_recall_at_k(_request(r).get("gold_ids", []), _response(r).get("retrieved_ids", []), k) for r in group_records]
            clause_ci = bootstrap_ci(clause)
            article_ci = bootstrap_ci(article)
            clause_ci["metric"] = f"clause_recall@{k}"
            article_ci["metric"] = f"article_recall@{k}"
            metrics[f"clause_recall@{k}"] = clause_ci
            metrics[f"article_recall@{k}"] = article_ci
        output[group] = metrics
    return output


def group_refusal(records: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for group in ("Nhóm 4", "Nhóm 5a", "Nhóm 5b", "Nhóm 5c", "Nhóm 5d"):
        group_records = [r for r in records if _group_name(r) == group]
        valid_records = [r for r in group_records if _response(r).get("status") != "error"]
        valid_records = [r for r in valid_records if is_out_of_scope(_request(r)) is not None and get_refused(_response(r)) is not None]
        valid_gold = [is_out_of_scope(_request(r)) for r in valid_records]
        pred = [get_refused(_response(r)) for r in valid_records]
        cm = build_confusion_matrix(valid_gold, pred)
        result = cm.to_dict()
        result["sample_size"] = len(group_records)
        result["status_error_count"] = sum(_response(r).get("status") == "error" for r in group_records)
        output[group] = result
    return output


def latency_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    def _calc_stats(values: list[float]) -> dict[str, Any]:
        if not values:
            return {"count": 0, "mean_ms": None, "median_ms": None, "p95_ms": None}
        return {
            "count": len(values),
            "mean_ms": float(np.mean(values)),
            "median_ms": float(median(values)),
            "p95_ms": float(np.percentile(values, 95)),
        }

    all_values = []
    gemini_values = []
    refusal_values = []

    for r in records:
        if _response(r).get("status") == "success" and _response(r).get("latency_ms") is not None:
            val = float(_response(r)["latency_ms"])
            all_values.append(val)
            refused = get_refused(_response(r))
            if refused:
                refusal_values.append(val)
            elif refused is False:
                gemini_values.append(val)

    return {
        "overall": _calc_stats(all_values),
        "gemini_called": _calc_stats(gemini_values),
        "refusal_gate": _calc_stats(refusal_values),
    }


def classify_errors(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors = []
    for record in records:
        request = _request(record)
        response = _response(record)
        if response.get("status") == "error":
            error_text = str(response.get("error", "")).lower()
            category = "API/Network Error" if re.search(r"api|network|timeout|quota|429|gemini", error_text) else "Other/Unknown"
            evidence = [response.get("error", "")]
        elif is_out_of_scope(request) is not None and get_refused(response) is not None and is_out_of_scope(request) != get_refused(response):
            if is_out_of_scope(request):
                category, evidence = "Scope/Refusal Error", ["out-of-scope request was answered (False Accept)"]
            else:
                gold_ids = set(request.get("gold_ids", []))
                retrieved_ids = set(response.get("retrieved_ids", []))
                if not gold_ids or not gold_ids.intersection(retrieved_ids):
                    category, evidence = "Retrieval Error", ["gold document absent from retrieved_ids causing refusal"]
                else:
                    category, evidence = "Scope/Refusal Error", ["in-scope request was refused despite correct context"]
        else:
            continue
        errors.append({"question_id": request.get("id"), "group": request.get("group"), "category": category, "evidence": evidence})
    return errors


def analyze_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    errors = classify_errors(records)
    return {
        "group_retrieval": group_retrieval(records),
        "group_refusal": group_refusal(records),
        "latency": latency_summary(records),
        "retry": {
            "observed_retry_count": sum(int(_response(r).get("retry_count", 0) or 0) for r in records),
            "records_with_retry": sum(int(_response(r).get("retry_count", 0) or 0) > 0 for r in records),
        },
        "error_analysis": errors,
        "error_counts": dict(Counter(item["category"] for item in errors)),
    }