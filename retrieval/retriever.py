"""
retrieval/retriever.py

Điểm truy hồi dữ liệu (Retriever) kết hợp tìm kiếm vector tương đồng
và bộ lọc trạng thái hiệu lực pháp lý của điều khoản.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
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


def retrieve_bm25(
    query: str,
    provisions: list[Provision],
    bm25_index,
    top_k: int = 5,
) -> list[RetrievalHit]:
    """Truy hồi bằng chỉ mục BM25Okapi (Sparse Retrieval) — baseline Sparse.

    Hàm này được xây dựng để so sánh với Dense Retrieval (FAISS).
    Cùng lọc theo `status='hieu_luc'` như `retrieve()` để đảm bảo kết quả đồng nhất.

    Args:
        query: Câu hỏi của người dùng.
        provisions: Danh sách tất cả Provision.
        bm25_index: Chỉ mục Bm25Index.
        top_k: Số lượng kết quả cần lấy.

    Returns:
        list[RetrievalHit]: Danh sách kết quả BM25 đã lọc trạng thái hiệu lực.
    """
    by_id = {p.provision_id: p for p in provisions}
    raw_hits = bm25_index.search(query, top_k=top_k)

    hits: list[RetrievalHit] = []
    for pid, score in raw_hits:
        prov = by_id.get(pid)
        if prov is None:
            continue
        if prov.status not in VALID_STATUSES_FOR_ANSWERING:
            continue
        hits.append(RetrievalHit(provision=prov, score=float(score)))
    return hits


def evaluate_retriever_recall(
    eval_dataset: list[dict],
    provisions: list[Provision],
    embedder: Embedder,
    faiss_index: FaissFlatIndex,
    k: int = 5,
    bm25_index=None,
    mode: Literal["faiss", "bm25", "both"] = "faiss",
) -> float | dict[str, float]:
    """Tính chỉ số Recall@k của retriever trên tập câu hỏi test.

    Args:
        eval_dataset: Danh sách các dict ('question', 'gold_provision_ids').
        provisions: Danh sách tất cả Provision.
        embedder: Mô hình embedding.
        faiss_index: Chỉ mục FAISS.
        k: Số lượng kết quả top-k.
        bm25_index: (Tùy chọn) Chỉ mục BM25 — cần thiết khi mode='bm25' hoặc 'both'.
        mode: 'faiss' (chỉ FAISS), 'bm25' (chỉ BM25), 'both' (trả về dict cả hai).

    Returns:
        float (mode='faiss'/'bm25') hoặc dict {'faiss': float, 'bm25': float} khi mode='both'.
    """
    from evaluation.metrics import recall_at_k

    recalls_faiss: list[float] = []
    recalls_bm25: list[float] = []

    for item in eval_dataset:
        gold_ids = item.get("gold_provision_ids", [])
        if not gold_ids:
            continue

        if mode in ("faiss", "both"):
            hits = retrieve(item["question"], provisions, embedder, faiss_index, top_k=k)
            retrieved_ids = [h.provision.provision_id for h in hits]
            r = recall_at_k(gold_ids, retrieved_ids, k=k)
            if not np.isnan(r):
                recalls_faiss.append(r)

        if mode in ("bm25", "both") and bm25_index is not None:
            bm25_hits = retrieve_bm25(item["question"], provisions, bm25_index, top_k=k)
            bm25_ids = [h.provision.provision_id for h in bm25_hits]
            r2 = recall_at_k(gold_ids, bm25_ids, k=k)
            if not np.isnan(r2):
                recalls_bm25.append(r2)

    if mode == "faiss":
        return float(np.mean(recalls_faiss)) if recalls_faiss else 0.0
    if mode == "bm25":
        return float(np.mean(recalls_bm25)) if recalls_bm25 else 0.0
    return {
        "faiss": float(np.mean(recalls_faiss)) if recalls_faiss else 0.0,
        "bm25": float(np.mean(recalls_bm25)) if recalls_bm25 else 0.0,
    }
