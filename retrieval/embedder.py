"""
retrieval/embedder.py

Module mã hóa văn bản (Embedding).
Sử dụng mô hình vietnamese-bi-encoder (SentenceTransformers),
tự động chuyển sang HashingFallbackEmbedder nếu không có kết nối tới HuggingFace.
"""
from __future__ import annotations

import hashlib
import re
from typing import Protocol
import numpy as np

import config


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Sử dụng mô hình vietnamese-bi-encoder để trích xuất vector ngữ nghĩa."""

    def __init__(self, model_name: str = config.EMBEDDING_MODEL_NAME):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, normalize_embeddings=True))


class HashingFallbackEmbedder:
    """Lớp fallback sinh vector dựa trên hashing khi chạy ở môi trường offline."""

    DIM = 384

    def __init__(self):
        self.model_name = "hashing-fallback"

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), self.DIM), dtype=np.float32)
        for i, t in enumerate(texts):
            vecs[i] = self._embed_one(t)
        return vecs

    def _embed_one(self, text: str) -> np.ndarray:
        v = np.zeros(self.DIM, dtype=np.float32)
        tokens = re.findall(r"\w+", text.lower())
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self.DIM
            sign = 1.0 if (h // self.DIM) % 2 == 0 else -1.0
            v[idx] += sign
        norm = np.linalg.norm(v)
        if norm > 0:
            v = v / norm
        return v


def get_embedder() -> Embedder:
    """Khởi tạo mô hình embedder thật hoặc lớp fallback nếu offline."""
    try:
        return SentenceTransformerEmbedder()
    except Exception as e:  # noqa: BLE001
        print(
            f"[Embedder] Không thể tải mô hình '{config.EMBEDDING_MODEL_NAME}' ({e}). "
            "Kích hoạt HashingFallbackEmbedder."
        )
        return HashingFallbackEmbedder()
