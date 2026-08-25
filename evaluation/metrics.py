"""evaluation/metrics.py

Các hàm tính toán chỉ số đánh giá cho hệ thống RAG:
- Recall@k cho phần tìm kiếm văn bản.
- Ma trận nhầm lẫn (Confusion Matrix) đánh giá năng lực của bộ lọc từ chối (Refusal Gate).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence
import numpy as np


def recall_at_k(actual_provisions: list[str], retrieved_provisions: list[str], k: int) -> float:
    """Tính tỷ lệ tìm đúng các đoạn luật trong top k kết quả."""
    if not actual_provisions:
        return 0.0
    top_k_retrieved = set(retrieved_provisions[:k])
    actual_set = set(actual_provisions)
    hits = len(actual_set.intersection(top_k_retrieved))
    return hits / len(actual_set)


@dataclass
class RefusalConfusionMatrix:
    """Bảng thống kê đánh giá khả năng lọc câu hỏi của Refusal Gate."""

    true_refusal: int = 0   # Từ chối đúng câu hỏi ngoài phạm vi (True Positive)
    false_accept: int = 0   # Chấp nhận nhầm câu hỏi ngoài phạm vi (False Negative)
    true_accept: int = 0    # Trả lời đúng câu hỏi trong phạm vi (True Negative)
    false_refusal: int = 0  # Từ chối nhầm câu hỏi trong phạm vi (False Positive)

    # Các alias tương thích
    @property
    def true_positive(self) -> int:
        return self.true_refusal

    @property
    def false_negative(self) -> int:
        return self.false_accept

    @property
    def true_negative(self) -> int:
        return self.true_accept

    @property
    def false_positive(self) -> int:
        return self.false_refusal

    @property
    def total(self) -> int:
        return self.true_refusal + self.false_accept + self.true_accept + self.false_refusal

    @property
    def trr(self) -> float:
        """Tỷ lệ từ chối đúng (True Refusal Rate) = TR / (TR + FA)."""
        denom = self.true_refusal + self.false_accept
        return self.true_refusal / denom if denom > 0 else 0.0

    @property
    def true_refusal_rate(self) -> float:
        return self.trr

    @property
    def frr(self) -> float:
        """Tỷ lệ từ chối nhầm (False Refusal Rate) = FR / (FR + TA)."""
        denom = self.false_refusal + self.true_accept
        return self.false_refusal / denom if denom > 0 else 0.0

    @property
    def false_refusal_rate(self) -> float:
        return self.frr

    @property
    def far(self) -> float:
        """Tỷ lệ chấp nhận nhầm câu ngoài phạm vi (False Acceptance Rate) = FA / (TR + FA)."""
        denom = self.true_refusal + self.false_accept
        return self.false_accept / denom if denom > 0 else 0.0

    @property
    def false_acceptance_rate(self) -> float:
        return self.far

    def to_dict(self) -> dict[str, float | int]:
        return {
            "true_refusal": self.true_refusal,
            "false_accept": self.false_accept,
            "true_accept": self.true_accept,
            "false_refusal": self.false_refusal,
            "total": self.total,
            "trr": round(self.trr * 100, 2),
            "frr": round(self.frr * 100, 2),
            "far": round(self.far * 100, 2),
        }

    def format_markdown_table(self) -> str:
        """Xuất bảng kết quả dưới dạng bảng Markdown."""
        lines = [
            "| Chỉ số | Giá trị | Ý nghĩa |",
            "| :--- | :---: | :--- |",
            f"| **True Refusal Rate (TRR)** | **{self.trr * 100:.2f}%** | Tỷ lệ từ chối đúng câu hỏi ngoài phạm vi |",
            f"| **False Refusal Rate (FRR)** | **{self.frr * 100:.2f}%** | Tỷ lệ từ chối nhầm câu hỏi hợp lệ |",
            f"| **False Acceptance Rate (FAR)** | **{self.far * 100:.2f}%** | Tỷ lệ chấp nhận nhầm câu hỏi ngoài phạm vi |",
        ]
        return "\n".join(lines)


def build_confusion_matrix(
    gold: Sequence[bool] | list[dict[str, Any]],
    pred: Sequence[bool] | None = None,
) -> RefusalConfusionMatrix:
    """Tạo ma trận nhầm lẫn từ kết quả dự đoán."""
    cm = RefusalConfusionMatrix()

    # Trường hợp truyền 2 danh sách boolean (gold và pred)
    if pred is not None:
        for g, p in zip(gold, pred):
            if g and p:
                cm.true_refusal += 1
            elif g and not p:
                cm.false_accept += 1
            elif not g and not p:
                cm.true_accept += 1
            else:
                cm.false_refusal += 1
        return cm

    # Trường hợp truyền danh sách dict kết quả đánh giá
    for item in gold:  # type: ignore[union-attr]
        if isinstance(item, dict):
            is_out = bool(item.get("is_out_of_scope", False))
            refused = bool(item.get("refused", item.get("should_refuse", False)))
            if is_out and refused:
                cm.true_refusal += 1
            elif is_out and not refused:
                cm.false_accept += 1
            elif not is_out and not refused:
                cm.true_accept += 1
            else:
                cm.false_refusal += 1

    return cm
