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

    def save(self, index_path: str | Path, model_name: str | None = None) -> None:
        """Lưu chỉ mục FAISS và danh sách _ids tương ứng xuống đĩa."""
        import faiss

        idx_p = Path(index_path)
        idx_p.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(idx_p))

        ids_path = Path(str(idx_p) + ".ids.json")
        ids_path.write_text(json.dumps(self._ids, ensure_ascii=False, indent=2), encoding="utf-8")
        metadata_path = Path(str(idx_p) + ".metadata.json")
        metadata_path.write_text(
            json.dumps(
                {"dimension": self.dim, "model_name": model_name, "provision_ids": self._ids},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(
        cls,
        index_path: str | Path,
        expected_dim: int | None = None,
        expected_ids: list[str] | None = None,
        expected_model_name: str | None = None,
    ) -> FaissFlatIndex:
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
        if len(ids) != index.ntotal:
            raise ValueError("FAISS index và mapping provision_id không cùng số lượng.")
        if len(ids) != len(set(ids)):
            raise ValueError("Mapping provision_id của FAISS index chứa ID trùng lặp.")
        if expected_dim is not None and index.d != expected_dim:
            raise ValueError(
                f"Dimension FAISS không khớp: index={index.d}, expected={expected_dim}."
            )
        if expected_ids is not None and ids != expected_ids:
            raise ValueError("Mapping provision_id của FAISS index không khớp corpus hiện tại.")
        metadata_path = Path(str(idx_p) + ".metadata.json")
        if expected_model_name is not None:
            if not metadata_path.exists():
                raise ValueError("FAISS index thiếu metadata model_name.")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("model_name") != expected_model_name:
                raise ValueError(
                    "Model của FAISS index không khớp embedder hiện tại: "
                    f"index={metadata.get('model_name')}, expected={expected_model_name}."
                )
        return instance

    def __len__(self) -> int:
        return len(self._ids)
