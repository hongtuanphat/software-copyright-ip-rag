"""
retrieval/faiss_index.py

Quản lý chỉ mục tìm kiếm vector Dense Retrieval sử dụng thư viện FAISS.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np


class FaissFlatIndex:
    """Chỉ mục FAISS dạng Flat Inner Product cho phép lưu trữ và tìm kiếm vector."""

    def __init__(self, dim: int):
        import faiss

        self.dim = dim
        self._index = faiss.IndexFlatIP(dim)
        self._ids: list[str] = []

    def add(self, vectors: np.ndarray, provision_ids: list[str]) -> None:
        """Thêm danh sách vector và provision_id tương ứng vào chỉ mục."""
        assert vectors.shape[0] == len(provision_ids)
        self._index.add(vectors.astype("float32"))
        self._ids.extend(provision_ids)

    def search(self, query_vec: np.ndarray, top_k: int) -> list[tuple[str, float]]:
        """Tìm kiếm top_k vector tương đồng nhất với query_vec."""
        query_vec = query_vec.astype("float32").reshape(1, -1)
        scores, idxs = self._index.search(query_vec, top_k)
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            results.append((self._ids[idx], float(score)))
        return results

    def save(self, index_path: str | Path) -> None:
        """Lưu chỉ mục FAISS và danh sách _ids tương ứng xuống đĩa."""
        import faiss

        idx_p = Path(index_path)
        idx_p.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(idx_p))

        ids_path = Path(str(idx_p) + ".ids.json")
        ids_path.write_text(json.dumps(self._ids, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, index_path: str | Path) -> FaissFlatIndex:
        """Nạp chỉ mục FAISS và danh sách _ids từ đĩa."""
        import faiss

        idx_p = Path(index_path)
        if not idx_p.exists():
            raise FileNotFoundError(f"Không tìm thấy chỉ mục FAISS tại {idx_p}")

        index = faiss.read_index(str(idx_p))
        ids_path = Path(str(idx_p) + ".ids.json")
        if ids_path.exists():
            ids = json.loads(ids_path.read_text(encoding="utf-8"))
        else:
            ids = []

        instance = cls(dim=index.d)
        instance._index = index
        instance._ids = ids
        return instance

    def __len__(self) -> int:
        return len(self._ids)
