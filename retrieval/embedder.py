"""SentenceTransformer embedding with strict initialization."""
from __future__ import annotations

from typing import Protocol
import numpy as np

import config
from ingestion.utils import tokenize_vietnamese


class Embedder(Protocol):
    model_name: str

    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Sử dụng mô hình vietnamese-bi-encoder để trích xuất vector ngữ nghĩa."""

    def __init__(self, model_name: str = config.EMBEDDING_MODEL_NAME):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        self._model.max_seq_length = config.MAX_SEQ_LENGTH

    def encode(self, texts: list[str]) -> np.ndarray:
        segmented_texts = [tokenize_vietnamese(text) for text in texts]
        vecs = self._model.encode(segmented_texts, normalize_embeddings=True)
        return np.asarray(vecs, dtype=np.float32)


def get_embedder() -> Embedder:
    """Initialize the configured embedder or fail loudly."""
    try:
        return SentenceTransformerEmbedder()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"Không thể tải embedder '{config.EMBEDDING_MODEL_NAME}'."
        ) from e
