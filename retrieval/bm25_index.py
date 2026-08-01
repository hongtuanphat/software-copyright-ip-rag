"""
retrieval/bm25_index.py

Tìm kiếm thông tin theo từ khóa Sparse Retrieval sử dụng thuật toán BM25Okapi.
"""
from __future__ import annotations

import re
from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class Bm25Index:
    """Chỉ mục BM25Okapi cho phép tìm kiếm văn bản dựa trên tần suất từ khóa."""

    def __init__(self, texts: list[str], provision_ids: list[str]):
        assert len(texts) == len(provision_ids)
        self._ids = provision_ids
        self._tokenized = [_tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(self._tokenized)

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Tìm kiếm top_k văn bản có điểm số BM25 cao nhất với query."""
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self._ids, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
