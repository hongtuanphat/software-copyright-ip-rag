"""
retrieval/retriever.py

Điểm truy hồi dữ liệu (Retriever) kết hợp tìm kiếm vector tương đồng
và bộ lọc trạng thái hiệu lực pháp lý của điều khoản.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from ingestion.chunker import Provision
from retrieval.embedder import Embedder
from retrieval.faiss_index import FaissFlatIndex

VALID_STATUSES_FOR_ANSWERING = {"hieu_luc"}


@dataclass
class RetrievalHit:
    provision: Provision
    score: float


def retrieve(
    query: str,
    provisions: list[Provision],
    embedder: Embedder,
    faiss_index: FaissFlatIndex,
    top_k: int = 5,
) -> list[RetrievalHit]:
    """Truy hồi các điều khoản pháp lý phù hợp nhất với câu hỏi đầu vào.

    Lọc bỏ các điều khoản không còn hiệu lực pháp lý (status != 'hieu_luc').

    Args:
        query: Câu hỏi của người dùng.
        provisions: Danh sách tất cả Provision.
        embedder: Đối tượng mô hình embedding.
        faiss_index: Chỉ mục FAISS.
        top_k: Số lượng kết quả cần lấy.

    Returns:
        list[RetrievalHit]: Danh sách kết quả truy hồi đạt yêu cầu.
    """
    by_id = {p.provision_id: p for p in provisions}
    query_vec = embedder.encode([query])[0]
    raw_hits = faiss_index.search(np.asarray(query_vec), top_k=top_k)

    hits: list[RetrievalHit] = []
    for pid, score in raw_hits:
        prov = by_id.get(pid)
        if prov is None:
            continue
        if prov.status not in VALID_STATUSES_FOR_ANSWERING:
            continue
        hits.append(RetrievalHit(provision=prov, score=score))
    return hits
