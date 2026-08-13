"""
evaluation/metrics.py

Tính toán các chỉ số đánh giá cho hệ thống RAG:
- Ma trận nhầm lẫn từ chối (Refusal Confusion Matrix): TRR, FRR, FAR.
- Mức độ truy hồi (Recall@k).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RefusalConfusionMatrix:
    true_accept: int = 0
    false_refusal: int = 0
    false_accept: int = 0
    true_refusal: int = 0

    @property
    def trr(self) -> float:
        denom = self.true_refusal + self.false_accept
        return self.true_refusal / denom if denom else float("nan")

    @property
    def frr(self) -> float:
        denom = self.false_refusal + self.true_accept
        return self.false_refusal / denom if denom else float("nan")

    @property
    def far(self) -> float:
        denom = self.false_accept + self.true_refusal
        return self.false_accept / denom if denom else float("nan")


def build_confusion_matrix(
    gold_should_refuse: list[bool], predicted_refused: list[bool]
) -> RefusalConfusionMatrix:
    """Tạo ma trận nhầm lẫn đánh giá cơ chế từ chối."""
    assert len(gold_should_refuse) == len(predicted_refused)
    cm = RefusalConfusionMatrix()
    for gold_refuse, pred_refuse in zip(gold_should_refuse, predicted_refused):
        if gold_refuse and pred_refuse:
            cm.true_refusal += 1
        elif gold_refuse and not pred_refuse:
            cm.false_accept += 1
        elif not gold_refuse and pred_refuse:
            cm.false_refusal += 1
        else:
            cm.true_accept += 1
    return cm


def recall_at_k(gold_ids: list[str], retrieved_ids: list[str], k: int) -> float:
    """Tính chỉ số Recall@k cho một câu hỏi."""
    if not gold_ids:
        return float("nan")
    if k <= 0:
        return 0.0

    gold_set = set(gold_ids)
    top_k_ids = set(retrieved_ids[:k])
    if not gold_set:
        return float("nan")

    return len(gold_set & top_k_ids) / len(gold_set)
