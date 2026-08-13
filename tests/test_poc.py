"""
tests/test_poc.py

Kiểm thử tự động cho các thành phần cốt lõi của pipeline RAG:
chunking (cấp Điều/Khoản), metadata, retrieval status filter, refusal gate, citation và metrics.
Chạy bộ test: pytest tests/ -v
"""
import numpy as np
import pytest

import config
from ingestion.chunker import parse_law_text, Provision
from ingestion.metadata import attach_effective_metadata, load_law_meta
from retrieval.embedder import HashingFallbackEmbedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import retrieve
from generation.refusal_gate import decide
from generation.citation import build_citations
from evaluation.metrics import build_confusion_matrix, recall_at_k


RAW_PATH = config.DATA_RAW_DIR / "67-VBHN-VPQH.txt"
SOURCE_URL = "https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-67-vbhn-vpqh-469197.htm"


@pytest.fixture(scope="module")
def provisions() -> list[Provision]:
    text = RAW_PATH.read_text(encoding="utf-8")
    provs = parse_law_text(text, law_code=config.LAW_CODE, source_url=SOURCE_URL)
    law_meta = load_law_meta(RAW_PATH)
    return attach_effective_metadata(provs, law_meta)


def test_chunker_splits_articles(provisions):
    assert len(provisions) == 55
    ids = [p.provision_id for p in provisions]
    assert len(ids) == len(set(ids)), "provision_id phải duy nhất"


@pytest.mark.parametrize(
    "art_no, expected_clause_count, expected_first_id",
    [
        ("22", 2, "67-VBHN-VPQH_Art22_Kh1"),
        ("13", 2, "67-VBHN-VPQH_Art13_Kh1"),
        ("19", 4, "67-VBHN-VPQH_Art19_Kh1"),
        ("25", 4, "67-VBHN-VPQH_Art25_Kh1"),
        ("39", 2, "67-VBHN-VPQH_Art39_Kh1"),
    ],
)
def test_chunker_splits_clauses(provisions, art_no, expected_clause_count, expected_first_id):
    clauses = [p for p in provisions if p.article_no == art_no and p.clause_no is not None]
    assert len(clauses) == expected_clause_count
    assert clauses[0].provision_id == expected_first_id


def test_chunker_flags_distractor_after_marker(provisions):
    art22 = next(p for p in provisions if p.article_no == "22")
    art58 = next(p for p in provisions if p.article_no == "58")
    assert art22.is_distractor is False
    assert art58.is_distractor is True
    assert art58.topic == "sang_che"


def test_effective_metadata_attached(provisions):
    for p in provisions:
        assert p.effective_from == "2026-03-23"
        assert p.status == "hieu_luc"
        assert p.last_checked_at is not None


def test_retriever_filters_out_of_effect_status(provisions):
    embedder = HashingFallbackEmbedder()
    texts = [p.text for p in provisions]
    vecs = embedder.encode(texts)
    idx = FaissFlatIndex(vecs.shape[1])
    idx.add(np.asarray(vecs), [p.provision_id for p in provisions])

    for p in provisions:
        if p.article_no == "22":
            p.status = "het_hieu_luc"

    hits = retrieve(
        "chương trình máy tính", provisions, embedder, idx, top_k=len(provisions)
    )
    assert all(h.provision.article_no != "22" for h in hits)

    for p in provisions:
        if p.article_no == "22":
            p.status = "hieu_luc"


def test_refusal_gate_refuses_when_no_hits():
    decision = decide("query bất kỳ", [])
    assert decision.should_refuse is True


def test_refusal_gate_out_of_scope_keyword():
    decision = decide("Xử phạt vi phạm giao thông xe máy vượt đèn đỏ như thế nào?", [])
    assert decision.should_refuse is True
    assert "ngoài phạm vi" in decision.reason


def test_refusal_gate_distractor_ratio(provisions):
    from retrieval.retriever import RetrievalHit

    # Tạo list hits với 80% distractor (4 distractor, 1 in-scope)
    distractors = [p for p in provisions if p.is_distractor][:4]
    in_scope = [p for p in provisions if not p.is_distractor][:1]
    hits = [RetrievalHit(provision=p, score=0.8) for p in distractors + in_scope]
    decision = decide("Quyền tác giả", hits)
    assert decision.should_refuse is True
    assert "dữ liệu nhiễu" in decision.reason


def test_citations_exclude_distractor(provisions):
    from retrieval.retriever import RetrievalHit

    hits = [
        RetrievalHit(provision=p, score=0.9)
        for p in provisions
        if p.article_no in ("22", "58")
    ]
    citations = build_citations(hits)
    cited_articles = {c["article_no"] for c in citations}
    assert "58" not in cited_articles
    assert "22" in cited_articles


def test_confusion_matrix_and_recall():
    gold = [True, False, False, True]
    pred = [True, False, True, False]
    cm = build_confusion_matrix(gold, pred)
    assert cm.true_refusal == 1
    assert cm.false_accept == 1
    assert cm.false_refusal == 1
    assert cm.true_accept == 1
    assert 0.0 <= cm.trr <= 1.0

    assert recall_at_k(["a", "b"], ["x", "a"], k=2) == 0.5
    assert recall_at_k(["a"], ["x", "y"], k=2) == 0.0
    assert recall_at_k(["a", "b", "c"], ["x", "b", "a", "y"], k=2) == 1 / 3
