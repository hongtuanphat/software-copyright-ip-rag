"""retrieval/bm25_index.py

Tìm kiếm thông tin theo từ khóa Sparse Retrieval sử dụng thuật toán BM25Okapi.
Hỗ trợ tách từ đơn (unigram) kết hợp từ ghép đôi (bigram) giúp cải thiện độ nhạy với cụm từ tiếng Việt.
"""
from __future__ import annotations

import re
from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    """Tách từ đơn và từ ghép đôi liền kề (unigram + bigram) để nắm bắt cụm từ pháp lý tiếng Việt."""
    words = re.findall(r"\w+", text.lower())
    if not words:
        return []
    bigrams = [f"{words[i]}_{words[i+1]}" for i in range(len(words) - 1)]
    return words + bigrams


class Bm25Index:
    """Chỉ mục BM25Okapi cho phép tìm kiếm văn bản dựa trên tần suất từ khóa."""

    def __init__(self, texts: list[str], provision_ids: list[str]):
        assert len(texts) == len(provision_ids)
        self._ids = provision_ids
        self._tokenized = [_tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(self._tokenized)

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Tìm kiếm top_k văn bản có điểm số BM25 cao nhất với query."""
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(zip(self._ids, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def __len__(self) -> int:
        return len(self._ids)
