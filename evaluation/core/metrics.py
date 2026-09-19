"""evaluation/metrics.py

Các hàm tính toán chỉ số đánh giá cho hệ thống RAG:
- Recall@k cho tầng tìm kiếm văn bản (ở cả 2 cấp độ: Cấp Khoản chính xác và Cấp Điều phân cấp).
- Ma trận nhầm lẫn (Confusion Matrix) đánh giá năng lực của bộ lọc từ chối (Refusal Gate).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence
import numpy as np


def recall_at_k(actual_provisions: list[str], retrieved_provisions: list[str], k: int) -> float:
    """Tính tỷ lệ tìm đúng các đoạn luật trong top k kết quả ở cấp độ chính xác (Exact Clause Match)."""
    if not actual_provisions:
        return 0.0
    top_k_retrieved = set(retrieved_provisions[:k])
    actual_set = set(actual_provisions)
    hits = len(actual_set.intersection(top_k_retrieved))
    return hits / len(actual_set)


def hierarchical_article_recall_at_k(actual_provisions: list[str], retrieved_provisions: list[str], k: int) -> float:
    """Tính Recall@k ở cấp độ Điều luật (Hierarchical Article Match) để chẩn đoán lỗi."""
    if not actual_provisions:
        return 0.0

    def to_article_id(pid: str) -> str:
        match = re.search(r"^(.+?_Art\d+[a-zA-Z]?)", pid)
        return match.group(1) if match else pid

    gold_articles = {to_article_id(gid) for gid in actual_provisions}
    top_k_articles = {to_article_id(rid) for rid in retrieved_provisions[:k]}

    hits = len(gold_articles.intersection(top_k_articles))
    return hits / len(gold_articles)


@dataclass
class RefusalConfusionMatrix:
    """Bảng thống kê đánh giá khả năng lọc câu hỏi của Refusal Gate."""

    true_refusal: int = 0   # Từ chối đúng câu hỏi ngoài phạm vi (True Positive)
    false_accept: int = 0   # Chấp nhận nhầm câu hỏi ngoài phạm vi (False Negative)
    true_accept: int = 0    # Trả lời đúng câu hỏi trong phạm vi (True Negative)
    false_refusal: int = 0  # Từ chối nhầm câu hỏi trong phạm vi (False Positive)

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
    for item in gold: 
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


def extract_citations_from_text(text: str) -> set[str]:
    """Tìm tất cả các ID định dạng Art... trong văn bản."""
    if not text:
        return set()
    matches = re.findall(r"Art\d+(?:_[a-zA-Z0-9_]+)?", text)
    return set(matches)


def extract_article_level(citations: set[str]) -> set[str]:
    """Chuyển đổi danh sách ID thành cấp độ Điều luật (Article) để chẩn đoán."""
    articles = set()
    for c in citations:
        m = re.search(r"^(.+?_Art\d+[a-zA-Z]?)", c)
        if m:
            articles.add(m.group(1))
        else:
            articles.add(c)
    return articles


@dataclass
class CitationMetricsReport:
    """Bảng thống kê đánh giá chỉ số Citation Exact Match (CEM)."""
    eval_records: int = 0
    exact_match_count: int = 0
    total_precision: float = 0.0
    total_recall: float = 0.0

    # Cấp độ Article (Điều)
    article_exact_match_count: int = 0
    article_total_precision: float = 0.0
    article_total_recall: float = 0.0

    def add_record(self, gold_ids: set[str], pred_ids: set[str], gold_art_ids: set[str], pred_art_ids: set[str]) -> None:
        self.eval_records += 1

        # Cấp độ Exact ID
        if pred_ids == gold_ids:
            self.exact_match_count += 1
            
        intersection = gold_ids.intersection(pred_ids)
        self.total_precision += len(intersection) / len(pred_ids) if pred_ids else 0.0
        self.total_recall += len(intersection) / len(gold_ids) if gold_ids else 0.0

        # Cấp độ Article
        if pred_art_ids == gold_art_ids:
            self.article_exact_match_count += 1
            
        intersection_art = gold_art_ids.intersection(pred_art_ids)
        self.article_total_precision += len(intersection_art) / len(pred_art_ids) if pred_art_ids else 0.0
        self.article_total_recall += len(intersection_art) / len(gold_art_ids) if gold_art_ids else 0.0

    def to_dict(self) -> dict[str, float | int]:
        if self.eval_records == 0:
            return {}
        return {
            "eval_records": self.eval_records,
            "exact_match_rate": round((self.exact_match_count / self.eval_records) * 100, 2),
            "citation_precision": round((self.total_precision / self.eval_records) * 100, 2),
            "citation_recall": round((self.total_recall / self.eval_records) * 100, 2),
            "article_exact_match_rate": round((self.article_exact_match_count / self.eval_records) * 100, 2),
            "article_citation_precision": round((self.article_total_precision / self.eval_records) * 100, 2),
            "article_citation_recall": round((self.article_total_recall / self.eval_records) * 100, 2),
        }
