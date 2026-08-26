"""retrieval/retriever.py

Các hàm tìm kiếm văn bản pháp luật:
- Tìm kiếm ngữ nghĩa bằng vector (FAISS Index).
- Tìm kiếm từ khóa chính xác (BM25Okapi).
- Tìm kiếm kết hợp (Hybrid Search) dùng thuật toán RRF.
- Lọc bỏ các điều khoản đã hết hiệu lực.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

import config
from ingestion.chunker import Provision
from retrieval.bm25_index import Bm25Index
from retrieval.embedder import Embedder
from retrieval.faiss_index import FaissFlatIndex


@dataclass
class RetrievalHit:
    """Chứa thông tin đoạn luật tìm được và điểm số tương ứng."""
    provision: Provision
    score: float


def retrieve(
    query: str,
    provisions: list[Provision],
    embedder: Embedder,
    faiss_index: FaissFlatIndex,
    top_k: int = config.TOP_K,
    filter_status: bool = True,
) -> list[RetrievalHit]:
    """Tìm kiếm theo vector tương đồng (Dense FAISS)."""
    q_vec = embedder.encode([query])
    raw_results = faiss_index.search(q_vec, top_k=min(len(provisions), top_k * 3))

    by_id = {p.provision_id: p for p in provisions}
    hits: list[RetrievalHit] = []

    for pid, score in raw_results:
        if pid not in by_id:
            continue
        p = by_id[pid]
        if filter_status and p.status != config.EFFECTIVE_STATUS_VALID:
            continue
        hits.append(RetrievalHit(provision=p, score=float(score)))
        if len(hits) >= top_k:
            break

    return hits


def retrieve_bm25(
    query: str,
    provisions: list[Provision],
    bm25_index: Bm25Index,
    top_k: int = config.TOP_K,
    filter_status: bool = True,
) -> list[RetrievalHit]:
    """Tìm kiếm theo từ khóa trùng khớp (BM25Okapi)."""
    raw_results = bm25_index.search(query, top_k=min(len(provisions), top_k * 3))
    by_id = {p.provision_id: p for p in provisions}
    hits: list[RetrievalHit] = []

    for pid, score in raw_results:
        if pid not in by_id:
            continue
        p = by_id[pid]
        if filter_status and p.status != config.EFFECTIVE_STATUS_VALID:
            continue
        hits.append(RetrievalHit(provision=p, score=float(score)))
        if len(hits) >= top_k:
            break

    return hits


def retrieve_hybrid(
    query: str,
    provisions: list[Provision],
    embedder: Embedder,
    faiss_index: FaissFlatIndex,
    bm25_index: Bm25Index,
    top_k: int = config.TOP_K,
    candidate_pool_size: int = config.CANDIDATE_POOL_SIZE,
    rrf_k: int = config.RRF_K,
    filter_status: bool = True,
    min_dense_score: float = config.MIN_SCORE_TIN_CAY,
) -> list[RetrievalHit]:
    """Tìm kiếm kết hợp (Hybrid Search) giữa FAISS và BM25 bằng thuật toán RRF.

    Dùng điểm Cosine của FAISS làm ngưỡng kiểm tra: nếu câu hỏi gõ linh tinh hoặc
    không liên quan đến luật (điểm cao nhất < 0.35) thì trả về rỗng để kích hoạt từ chối.
    """
    by_id = {p.provision_id: p for p in provisions}
    pool_k = min(len(provisions), candidate_pool_size)

    # 1. Tìm các ứng viên bằng vector FAISS
    q_vec = embedder.encode([query])
    dense_raw = faiss_index.search(q_vec, top_k=pool_k)

    # Kiểm tra điểm tương đồng cao nhất của câu hỏi
    max_dense_score = dense_raw[0][1] if dense_raw else 0.0
    if max_dense_score < min_dense_score:
        return []

    dense_ranked_ids: list[str] = []
    for pid, score in dense_raw:
        # Chỉ lấy các vector có độ tương quan dương
        if score > 0.0 and pid in by_id:
            p = by_id[pid]
            if not filter_status or p.status == config.EFFECTIVE_STATUS_VALID:
                dense_ranked_ids.append(pid)

    # 2. Tìm các ứng viên bằng từ khóa BM25
    bm25_raw = bm25_index.search(query, top_k=pool_k)
    bm25_ranked_ids: list[str] = []
    for pid, score in bm25_raw:
        if score > 0 and pid in by_id:
            p = by_id[pid]
            if not filter_status or p.status == config.EFFECTIVE_STATUS_VALID:
                bm25_ranked_ids.append(pid)

    # 3. Tính điểm xếp hạng kết hợp theo công thức RRF (Reciprocal Rank Fusion)
    rrf_scores: dict[str, float] = {}

    # Cộng điểm từ nhánh vector
    for rank, pid in enumerate(dense_ranked_ids, 1):
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + (1.0 / (rrf_k + rank))

    # Cộng điểm từ nhánh từ khóa
    for rank, pid in enumerate(bm25_ranked_ids, 1):
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + (1.0 / (rrf_k + rank))

    # 4. Sắp xếp các đoạn luật theo điểm RRF giảm dần
    sorted_pids = sorted(rrf_scores.keys(), key=lambda pid: rrf_scores[pid], reverse=True)

    hits: list[RetrievalHit] = []
    for pid in sorted_pids[:top_k]:
        p = by_id[pid]
        final_score = rrf_scores[pid]
        hits.append(RetrievalHit(provision=p, score=round(final_score, 6)))

    return hits


def evaluate_retriever_recall(
    test_queries: list[dict],
    provisions: list[Provision],
    embedder: Embedder,
    faiss_index: FaissFlatIndex,
    bm25_index: Bm25Index | None = None,
    top_k: int = config.TOP_K,
    k: int | None = None,
    mode: str = "hybrid",
) -> float:
    """Hàm phụ trợ tính tỷ lệ Recall@k trên một tập câu hỏi mẫu."""
    eff_k = k if k is not None else top_k
    hits_per_query = []
    for item in test_queries:
        q = item.get("question", "")
        raw_gold = (
            item.get("gold_provision_ids")
            or item.get("ground_truth_provisions")
            or item.get("gold_ids")
            or []
        )
        gold_ids = set(raw_gold)
        if not gold_ids:
            continue

        if mode == "hybrid" and bm25_index is not None:
            res = retrieve_hybrid(q, provisions, embedder, faiss_index, bm25_index, top_k=eff_k, min_dense_score=0.0)
        elif mode == "bm25" and bm25_index is not None:
            res = retrieve_bm25(q, provisions, bm25_index, top_k=eff_k)
        else:
            res = retrieve(q, provisions, embedder, faiss_index, top_k=eff_k)

        retrieved_ids = [h.provision.provision_id for h in res]
        matched = len(gold_ids.intersection(retrieved_ids))
        hits_per_query.append(matched / len(gold_ids))

    if not hits_per_query:
        return 0.0

    return round(float(np.mean(hits_per_query)), 4)
