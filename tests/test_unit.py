"""tests/test_unit.py

Unit tests cho các module cơ bản: build_index_text, tokenization, citation parser, và RRF logic.
"""
from __future__ import annotations

import numpy as np
import pytest

from ingestion.chunker import Provision
from ingestion.utils import build_index_text, tokenize_vietnamese

from retrieval.retriever import retrieve_hybrid, RetrievalHit


def _make_p(
    provision_id: str,
    law_code: str = "L1",
    article_no: str = "1",
    clause_no: str | None = None,
    title: str = "T",
    text: str = "T",
    status: str = "hieu_luc",
    is_distractor: bool = False,
) -> Provision:
    return Provision(
        provision_id=provision_id,
        law_code=law_code,
        article_no=article_no,
        clause_no=clause_no,
        title=title,
        text=text,
        topic="test",
        is_distractor=is_distractor,
        source_url="http://test",
        status=status,
    )


def test_build_index_text():
    p1 = _make_p(
        provision_id="P1",
        law_code="17/2023/ND-CP",
        article_no="5",
        clause_no="2",
        title="Tiêu đề mẫu",
        text="Nội dung khoản 2."
    )
    text1 = build_index_text(p1)
    assert text1 == "[17/2023/ND-CP] Điều 5. Tiêu đề mẫu Khoản 2. Nội dung khoản 2."

    p2 = _make_p(
        provision_id="P2",
        law_code="67/VBHN",
        article_no="10",
        clause_no=None,
        title="Tiêu đề 10",
        text="Nội dung điều 10."
    )
    text2 = build_index_text(p2)
    assert text2 == "[67/VBHN] Điều 10. Tiêu đề 10 Nội dung điều 10."


def test_tokenize_vietnamese():
    text = "quyền tác giả đối với chương trình máy tính"
    tokenized = tokenize_vietnamese(text)
    assert "chương_trình máy_tính" in tokenized or "chương_trình" in tokenized
    assert "tác_giả" in tokenized









class MockEmbedder:
    model_name = "mock"
    def encode(self, texts):
        return np.ones((len(texts), 2), dtype=np.float32)

class MockFaissIndex:
    def __init__(self, scores, pids):
        self.scores = scores
        self.pids = pids
    def search(self, q_vec, top_k):
        return list(zip(self.pids, self.scores))[:top_k]

class MockBm25Index:
    def __init__(self, scores, pids):
        self.scores = scores
        self.pids = pids
    def search(self, query, top_k):
        return list(zip(self.pids, self.scores))[:top_k]


def test_rrf_weighting_logic():
    p1 = _make_p(provision_id="P1", article_no="1")
    p2 = _make_p(provision_id="P2", article_no="2")
    p3 = _make_p(provision_id="P3", article_no="3")
    
    provisions = [p1, p2, p3]
    embedder = MockEmbedder()
    
    # Xếp hạng FAISS: P1 > P2 > P3
    faiss_idx = MockFaissIndex([0.9, 0.8, 0.7], ["P1", "P2", "P3"])
    
    # Xếp hạng BM25: P3 > P2 > P1
    bm25_idx = MockBm25Index([2.0, 1.5, 1.0], ["P3", "P2", "P1"])
    
    hits = retrieve_hybrid(
        query="test query không có thực thể",
        provisions=provisions,
        embedder=embedder,
        faiss_index=faiss_idx,
        bm25_index=bm25_idx,
        min_dense_score=0.1,  # cho phép pass gate
        rrf_k=15,
        enable_entity=False
    )
    
    assert len(hits) == 3
    
    # P1 rank: FAISS=1, BM25=3 -> 1/16 + 1/18 = 0.118055
    # P2 rank: FAISS=2, BM25=2 -> 1/17 + 1/17 = 0.117647
    # P3 rank: FAISS=3, BM25=1 -> 1/18 + 1/16 = 0.118055
    
    score_p1 = next(h.score for h in hits if h.provision.provision_id == "P1")
    score_p2 = next(h.score for h in hits if h.provision.provision_id == "P2")
    score_p3 = next(h.score for h in hits if h.provision.provision_id == "P3")
    
    assert round(score_p1, 5) == round(score_p3, 5)
    assert score_p1 > score_p2


def test_rrf_with_entity_boost():
    # P1 là Điều 10
    p1 = _make_p(provision_id="P1", article_no="10")
    p2 = _make_p(provision_id="P2", article_no="2")
    
    provisions = [p1, p2]
    embedder = MockEmbedder()
    
    # P2 luôn cao điểm hơn ở FAISS và BM25
    faiss_idx = MockFaissIndex([0.8, 0.9], ["P1", "P2"])
    bm25_idx = MockBm25Index([1.0, 2.0], ["P1", "P2"])
    
    # Truy vấn nhắc đến "Điều 10" sẽ trigger entity branch cho P1
    hits = retrieve_hybrid(
        query="căn cứ theo điều 10 của luật",
        provisions=provisions,
        embedder=embedder,
        faiss_index=faiss_idx,
        bm25_index=bm25_idx,
        min_dense_score=0.1,
        rrf_k=15,
        enable_entity=True
    )
    
    # P2: FAISS=1, BM25=1, Entity=None -> 1/16 + 1/16 = 0.125
    # P1: FAISS=2, BM25=2, Entity=1 -> 1/17 + 1/17 + 1/16 = 0.1801
    assert hits[0].provision.provision_id == "P1"
    assert hits[1].provision.provision_id == "P2"


def test_bm25_zero_score_is_not_retrieval_evidence():
    from types import SimpleNamespace
    from retrieval.retriever import retrieve_bm25

    provision = _make_p("P1")
    index = SimpleNamespace(search=lambda query, top_k: [("P1", 0.0)])

    assert retrieve_bm25("unrelated", [provision], index, top_k=1) == []


def test_hybrid_drops_candidate_that_only_has_zero_bm25_score():
    provisions = [_make_p("P1"), _make_p("P2", article_no="2")]
    embedder = MockEmbedder()
    faiss_index = MockFaissIndex([0.9], ["P1"])
    bm25_index = MockBm25Index([0.0], ["P2"])

    hits = retrieve_hybrid(
        "query",
        provisions,
        embedder,
        faiss_index,
        bm25_index,
        top_k=2,
        min_dense_score=0.1,
        enable_entity=False,
    )

    assert [hit.provision.provision_id for hit in hits] == ["P1"]
