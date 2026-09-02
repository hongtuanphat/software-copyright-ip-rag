"""tests/test_poc.py

Kiểm thử tự động cho các thành phần cốt lõi của pipeline RAG:
chunking (cấp Điều/Khoản), metadata, retrieval status filter, refusal gate, citation và metrics.
Chạy bộ test: pytest tests/ -v
"""
from __future__ import annotations

import copy
import json
import numpy as np
import pytest

import config
from pipeline import RAGPipeline, answer_rag
from ingestion.chunker import parse_law_text, Provision
from ingestion.metadata import attach_effective_metadata, load_law_meta
from retrieval.embedder import HashingFallbackEmbedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import retrieve, retrieve_bm25
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
    assert len(provisions) >= 55
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
    """Xác nhận retriever loại bỏ chunk có status != 'hieu_luc'.

    Dùng bản sao cục bộ (deep copy) của provisions để tránh
    nhiễm dữ liệu sang các test khác trong scope='module' nếu assert thất bại.
    """
    # Deep copy để không mutate fixture dùng chung
    local_provisions = copy.deepcopy(provisions)

    embedder = HashingFallbackEmbedder()
    texts = [p.text for p in local_provisions]
    vecs = embedder.encode(texts)
    idx = FaissFlatIndex(vecs.shape[1])
    idx.add(np.asarray(vecs), [p.provision_id for p in local_provisions])

    # Đặt Điều 22 thành het_hieu_luc trên bản sao cục bộ
    for p in local_provisions:
        if p.article_no == "22":
            p.status = "het_hieu_luc"

    hits = retrieve(
        "chương trình máy tính", local_provisions, embedder, idx, top_k=len(local_provisions)
    )
    assert all(h.provision.article_no != "22" for h in hits)
    # Fixture gốc 'provisions' không bị thay đổi
    original_art22 = [p for p in provisions if p.article_no == "22"]
    assert all(p.status == "hieu_luc" for p in original_art22)


def test_retrieve_bm25_filters_out_of_effect_status(provisions):
    """Xác nhận retrieve_bm25() cũng loại bỏ chunk hết hiệu lực giống retrieve()."""
    from retrieval.bm25_index import Bm25Index

    local_provisions = copy.deepcopy(provisions)
    texts = [p.text for p in local_provisions]
    p_ids = [p.provision_id for p in local_provisions]
    bm25 = Bm25Index(texts, p_ids)

    for p in local_provisions:
        if p.article_no == "22":
            p.status = "het_hieu_luc"

    hits = retrieve_bm25("chương trình máy tính bản sao dự phòng", local_provisions, bm25, top_k=len(local_provisions))
    assert all(h.provision.article_no != "22" for h in hits)


def test_embedder_encodes_texts():
    from retrieval.embedder import get_embedder

    embedder = get_embedder()
    texts = ["Quyền tác giả đối với chương trình máy tính", "Bản sao dự phòng phần mềm"]
    vecs = embedder.encode(texts)
    assert isinstance(vecs, np.ndarray)
    assert vecs.dtype == np.float32
    assert vecs.shape[0] == 2
    assert vecs.shape[1] in (384, 768)
    norms = np.linalg.norm(vecs, axis=1)
    np.testing.assert_allclose(norms, 1.0, rtol=1e-3)


def test_faiss_index_save_and_load(tmp_path):
    dim = 64
    idx_path = tmp_path / "test_faiss.index"

    idx_original = FaissFlatIndex(dim=dim)
    dummy_vecs = np.random.randn(5, dim).astype(np.float32)
    dummy_vecs /= np.linalg.norm(dummy_vecs, axis=1, keepdims=True)
    dummy_ids = [f"test_id_{i}" for i in range(5)]

    idx_original.add(dummy_vecs, dummy_ids)
    assert len(idx_original) == 5

    idx_original.save(idx_path)
    assert idx_path.exists()
    assert (tmp_path / "test_faiss.index.ids.json").exists()

    idx_loaded = FaissFlatIndex.load(idx_path)
    assert len(idx_loaded) == 5
    assert idx_loaded.dim == dim

    hits = idx_loaded.search(dummy_vecs[0], top_k=1)
    assert len(hits) == 1
    assert hits[0][0] == "test_id_0"


def test_vector_id_and_embedding_model_populated(provisions, tmp_path):
    from main import index_corpus

    tmp_chunks = tmp_path / "chunks.jsonl"
    tmp_index = tmp_path / "faiss.index"
    embedder, faiss_idx, bm25 = index_corpus(provisions, output_index_path=tmp_index, output_chunks_path=tmp_chunks)

    for i, p in enumerate(provisions):
        assert p.vector_id == i
        assert p.embedding_model is not None

    assert tmp_chunks.exists()
    lines = tmp_chunks.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(provisions)

    for i, line in enumerate(lines):
        data = json.loads(line)
        assert data["vector_id"] == i
        assert data["embedding_model"] is not None


def test_bm25_index_search(provisions):
    from retrieval.bm25_index import Bm25Index

    texts = [p.text for p in provisions]
    p_ids = [p.provision_id for p in provisions]
    bm25 = Bm25Index(texts, p_ids)

    assert len(bm25) == len(provisions)
    results = bm25.search("bản sao dự phòng", top_k=3)
    assert len(results) > 0
    top_pid = results[0][0]
    assert "Art22" in top_pid


def test_evaluate_retriever_recall(provisions, tmp_path):
    from retrieval.retriever import evaluate_retriever_recall
    from main import index_corpus

    tmp_chunks = tmp_path / "chunks.jsonl"
    tmp_index = tmp_path / "faiss.index"
    embedder, faiss_idx, _ = index_corpus(provisions, output_index_path=tmp_index, output_chunks_path=tmp_chunks)
    eval_set = [
        {
            "question": "Quyền tác giả đối với chương trình máy tính",
            "gold_provision_ids": ["67-VBHN-VPQH_Art22_Kh1"],
        },
        {
            "question": "tạo bản sao dự phòng chương trình máy tính",
            "gold_provision_ids": ["67-VBHN-VPQH_Art22_Kh1"],
        },
    ]
    recall = evaluate_retriever_recall(eval_set, provisions, embedder, faiss_idx, k=5)
    assert 0.0 <= recall <= 1.0
    assert recall > 0.0


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
# ==============================================================================
# Kiểm tra backend pipeline API và hàm helper dùng cho Streamlit UI
# ==============================================================================

def test_pipeline_api_initialization():
    pipeline = RAGPipeline()
    assert len(pipeline.provisions) >= 100
    assert pipeline.faiss_index is not None
    assert pipeline.embedder is not None


def test_pipeline_api_query_in_scope():
    pipeline = RAGPipeline()
    question = "Chương trình máy tính được bảo hộ dưới hình thức nào theo Luật Sở hữu trí tuệ?"
    res = pipeline.query(question)

    assert res.question == question
    assert res.is_refused is False
    assert len(res.answer) > 20
    assert len(res.citations) > 0
    assert res.execution_time_seconds > 0
    assert any("22" in str(c.get("article_no")) or "14" in str(c.get("article_no")) for c in res.citations)


def test_pipeline_api_query_refusal_out_of_scope():
    pipeline = RAGPipeline()
    question = "Mức xử phạt vượt đèn đỏ đối với xe máy là bao nhiêu?"
    res = pipeline.query(question)

    assert res.is_refused is True
    assert "ngoài phạm vi" in res.refusal_reason.lower() or "xe máy" in res.refusal_reason.lower()
    assert len(res.citations) == 0


def test_pipeline_api_answer_rag_helper():
    data = answer_rag("Điều 22 Luật Sở hữu trí tuệ quy định gì về bản sao dự phòng phần mềm?")
    assert isinstance(data, dict)
    assert "answer" in data
    assert "citations" in data
    assert "is_refused" in data
    assert data["is_refused"] is False
# ==============================================================================
# BỔ SUNG KIỂM THỬ CHO TUẦN 5 (HYBRID SEARCH, CRAWLER ALERTS, EXPANDED REFUSAL)
# ==============================================================================

def test_retrieve_hybrid_rrf_ranking(provisions, tmp_path):
    """Kiểm tra tính năng Hybrid Search kết hợp Dense FAISS và Sparse BM25."""
    from main import index_corpus
    from retrieval.retriever import retrieve_hybrid

    tmp_chunks = tmp_path / "chunks.jsonl"
    tmp_index = tmp_path / "faiss.index"
    embedder, faiss_idx, bm25_idx = index_corpus(provisions, output_index_path=tmp_index, output_chunks_path=tmp_chunks)
    query = "Quyền tác giả đối với chương trình máy tính gồm những quyền nào?"

    hits = retrieve_hybrid(
        query=query,
        provisions=provisions,
        embedder=embedder,
        faiss_index=faiss_idx,
        bm25_index=bm25_idx,
        top_k=5,
    )

    assert len(hits) == 5
    assert all(h.score > 0 for h in hits)
    # Kiểm tra điều luật quan trọng nhất (Điều 22 hoặc Điều 18, 19, 20) nằm trong top hits
    article_nos = [h.provision.article_no for h in hits]
    assert any(art in ["22", "18", "19", "20"] for art in article_nos)


def test_refusal_gate_expanded_out_of_scope_keywords():
    """Kiểm tra cơ chế từ chối với danh mục từ khóa mở rộng (đất đai, hôn nhân, hình sự)."""
    out_of_scope_queries = [
        "Thủ tục sang tên sổ đỏ nhà đất cần những giấy tờ gì?",
        "Mức phân chia tài sản khi ly hôn theo Luật Hôn nhân và gia đình?",
        "Hình phạt tù đối với tội phạm ma túy theo Bộ luật hình sự là bao nhiêu năm?",
        "Quy định về đóng bảo hiểm xã hội và trợ cấp thất nghiệp?",
    ]

    for q in out_of_scope_queries:
        decision = decide(q, hits=[])
        assert decision.should_refuse is True, f"Phải từ chối câu hỏi ngoài phạm vi: {q}"
        assert "ngoài phạm vi" in decision.reason.lower()


def test_monitoring_crawler_and_effective_alerts(tmp_path):
    """Kiểm tra module Crawler và phát cảnh báo hiệu lực văn bản sắp hết hạn."""
    from monitoring.crawler import CrawlResult
    from monitoring.effective_checker import apply_crawl_results, save_alerts, get_active_alerts
    from ingestion.chunker import Provision

    fake_provision = Provision(
        provision_id="67-VBHN-VPQH_Art22_Kh1",
        law_code="67/VBHN-VPQH",
        article_no="22",
        clause_no="1",
        title="Quyền tác giả",
        text="Nội dung điều luật...",
        topic="quyen_tac_gia_ctmt",
        is_distractor=False,
        source_url="https://congbao.chinhphu.vn/...",
        status="hieu_luc",
    )

    # Giả lập kết quả cào: văn bản sắp hết hiệu lực sau 20 ngày (trong ngưỡng 45 ngày)
    from datetime import datetime, timezone, timedelta
    future_date = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()

    crawl_res = CrawlResult(
        law_code="67/VBHN-VPQH",
        source_url="https://congbao.chinhphu.vn/...",
        crawled_at=datetime.now(timezone.utc).isoformat(),
        status="hieu_luc",
        effective_from="2026-03-23",
        effective_to=future_date,
        replaced_by=None,
        is_mock=True,
    )

    updated_provs, alerts = apply_crawl_results([crawl_res], [fake_provision])
    assert len(alerts) >= 1
    assert alerts[0]["alert_type"] == "EXPIRING_SOON"

    # Kiểm tra lưu và đọc alerts
    alerts_file = tmp_path / "alerts_test.jsonl"
    save_alerts(alerts, path=alerts_file)
    active = get_active_alerts(path=alerts_file)
    assert len(active) == len(alerts)
# ---------------------------------------------------------------------------
# Các bài kiểm tra cho Semantic Reranker & 2-Stage Retrieval (Tuần 6)
# ---------------------------------------------------------------------------
def test_cross_encoder_reranker(provisions):
    """Kiểm tra CrossEncoderReranker chấm điểm và xếp hạng lại danh sách hits."""
    from retrieval.reranker import CrossEncoderReranker
    from retrieval.retriever import RetrievalHit
    
    reranker = CrossEncoderReranker()
    sample_hits = [
        RetrievalHit(provision=provisions[0], score=0.1),
        RetrievalHit(provision=provisions[1], score=0.2),
    ]
    query = "Quyền tác giả phát sinh khi nào?"
    reranked = reranker.rerank(query, sample_hits, top_k=2)
    assert len(reranked) == 2
    assert isinstance(reranked[0], RetrievalHit)
    assert isinstance(reranked[0].score, float)


def test_retrieve_with_rerank_integration(provisions):
    """Kiểm tra hàm retrieve_with_rerank trả về top_k kết quả sau khi qua Reranker."""
    from retrieval.reranker import get_reranker
    from retrieval.retriever import retrieve_with_rerank
    from retrieval.bm25_index import Bm25Index
    from retrieval.embedder import HashingFallbackEmbedder
    from retrieval.faiss_index import FaissFlatIndex
    
    embedder = HashingFallbackEmbedder()
    faiss_index = FaissFlatIndex(dim=embedder.DIM)
    vecs = embedder.encode([p.text for p in provisions])
    pids = [p.provision_id for p in provisions]
    faiss_index.add(vecs, pids)
    bm25_index = Bm25Index([p.text for p in provisions], pids)
    
    reranker = get_reranker()
    query = "chương trình máy tính được bảo hộ như thế nào?"
    hits = retrieve_with_rerank(
        query=query,
        provisions=provisions,
        embedder=embedder,
        faiss_index=faiss_index,
        bm25_index=bm25_index,
        reranker=reranker,
        candidate_top_k=10,
        final_top_k=3,
        min_dense_score=0.0,
    )
    assert len(hits) <= 3
    assert all(h.provision.status == "hieu_luc" for h in hits)
