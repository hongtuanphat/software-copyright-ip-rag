"""retrieval/retriever.py

Các hàm tìm kiếm văn bản pháp luật:
- Tìm kiếm ngữ nghĩa bằng vector (FAISS Index).
- Tìm kiếm từ khóa chính xác (BM25Okapi).
- Tìm kiếm kết hợp (Hybrid Search) dùng thuật toán RRF.
- Lọc bỏ các điều khoản đã hết hiệu lực.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re
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

    # 3. Ưu tiên các đoạn luật khớp số Điều/Khoản nếu câu hỏi có nhắc tới
    dieu_match = re.search(r"\b(?:điều|dieu)\s+(\d+[a-zA-Z]?)\b", query, re.IGNORECASE)
    khoan_match = re.search(r"\b(?:khoản|khoan)\s+(\d+)\b", query, re.IGNORECASE)
    target_dieu = dieu_match.group(1).lower() if dieu_match else None
    target_khoan = khoan_match.group(1) if khoan_match else None

    entity_ranked_ids: list[str] = []
    if target_dieu or target_khoan:
        candidate_pool_set = list(dict.fromkeys(dense_ranked_ids + bm25_ranked_ids))
        entity_scored: list[tuple[str, int]] = []
        for pid in candidate_pool_set:
            p = by_id[pid]
            score_e = 0
            if target_dieu and p.article_no.lower() == target_dieu:
                score_e += 2
                if target_khoan and p.clause_no == target_khoan:
                    score_e += 3
            elif target_khoan and p.clause_no == target_khoan:
                score_e += 1
            if score_e > 0:
                entity_scored.append((pid, score_e))
        entity_scored.sort(key=lambda x: x[1], reverse=True)
        entity_ranked_ids = [x[0] for x in entity_scored]

    # 4. Kết hợp thứ hạng bằng thuật toán Reciprocal Rank Fusion (RRF)
    rrf_scores: dict[str, float] = {}

    # Điểm từ tìm kiếm vector (Dense)
    for rank, pid in enumerate(dense_ranked_ids, 1):
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + (1.0 / (rrf_k + rank))

    # Điểm từ tìm kiếm từ khóa (BM25)
    for rank, pid in enumerate(bm25_ranked_ids, 1):
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + (1.0 / (rrf_k + rank))

    # Điểm bổ sung nếu khớp Điều/Khoản cụ thể
    for rank, pid in enumerate(entity_ranked_ids, 1):
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + (1.0 / (rrf_k + rank))

    # 5. Sắp xếp các đoạn luật theo điểm RRF giảm dần
    sorted_pids = sorted(rrf_scores.keys(), key=lambda pid: rrf_scores[pid], reverse=True)

    hits: list[RetrievalHit] = []
    for pid in sorted_pids[:top_k]:
        p = by_id[pid]
        final_score = rrf_scores[pid]
        hits.append(RetrievalHit(provision=p, score=round(final_score, 6)))

    return hits
