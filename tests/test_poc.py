from pipeline import RAGPipeline, answer_rag
"""
tests/test_poc.py

Kiểm thử tự động cho các thành phần cốt lõi của pipeline RAG:
chunking (cấp Điều/Khoản), metadata, retrieval status filter, refusal gate, citation và metrics.
Chạy bộ test: pytest tests/ -v
"""
import copy
import json
import numpy as np
import pytest

import config
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


def test_vector_id_and_embedding_model_populated(provisions):
    from main import index_corpus

    embedder, faiss_idx, bm25 = index_corpus(provisions)

    for i, p in enumerate(provisions):
        assert p.vector_id == i
        assert p.embedding_model is not None

    assert config.CHUNKS_PATH.exists()
    lines = config.CHUNKS_PATH.read_text(encoding="utf-8").strip().splitlines()
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


def test_evaluate_retriever_recall(provisions):
    from retrieval.retriever import evaluate_retriever_recall
    from main import index_corpus

    embedder, faiss_idx, _ = index_corpus(provisions)
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
