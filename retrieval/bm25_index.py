"""BM25 sparse retrieval with Vietnamese word segmentation."""
from __future__ import annotations

from rank_bm25 import BM25Okapi
from ingestion.utils import tokenize_for_bm25


class Bm25Index:
    """Chỉ mục BM25Okapi cho phép tìm kiếm văn bản dựa trên tần suất từ khóa."""

    def __init__(self, texts: list[str], provision_ids: list[str]):
        assert len(texts) == len(provision_ids)
        self._ids = provision_ids
        self._tokenized = [tokenize_for_bm25(t) for t in texts]
        self._bm25 = BM25Okapi(self._tokenized)

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Tìm kiếm top_k văn bản có điểm số BM25 cao nhất với query."""
        tokens = tokenize_for_bm25(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(zip(self._ids, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def __len__(self) -> int:
        return len(self._ids)
