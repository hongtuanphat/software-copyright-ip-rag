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
from ingestion.utils import build_index_text, tokenize_vietnamese
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import retrieve, retrieve_bm25
from generation.refusal_gate import decide

from evaluation.core.metrics import build_confusion_matrix, recall_at_k


RAW_PATH = config.DATA_RAW_DIR / "67-VBHN-VPQH.txt"
SOURCE_URL = "https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-67-vbhn-vpqh-469197.htm"


class DeterministicTestEmbedder:
    """Small deterministic embedder used only to test FAISS filtering."""

    model_name = "test-embedder"

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), 8), dtype=np.float32)
        for row_index, text in enumerate(texts):
            for char_index, character in enumerate(text):
                vectors[row_index, (ord(character) + char_index) % 8] += 1.0
            norm = np.linalg.norm(vectors[row_index])
            if norm:
                vectors[row_index] /= norm
        return vectors


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


def test_build_index_text_and_vietnamese_tokenization(provisions):
    provision = next(p for p in provisions if p.article_no == "22" and p.clause_no == "1")
    index_text = build_index_text(provision)

    assert index_text.startswith("[67/VBHN-VPQH] Điều 22.")
    assert "Khoản 1." in index_text
    assert provision.text in index_text
    assert "chương_trình" in tokenize_vietnamese("chương trình máy tính")


def test_retriever_filters_out_of_effect_status(provisions):
    """Xác nhận retriever loại bỏ chunk có status != 'hieu_luc'.

    Dùng bản sao cục bộ (deep copy) của provisions để tránh
    nhiễm dữ liệu sang các test khác trong scope='module' nếu assert thất bại.
    """
    # Deep copy để không mutate fixture dùng chung
    local_provisions = copy.deepcopy(provisions)

    embedder = DeterministicTestEmbedder()
    texts = [build_index_text(p) for p in local_provisions]
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
    texts = [build_index_text(p) for p in local_provisions]
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

    texts = [build_index_text(p) for p in provisions]
    p_ids = [p.provision_id for p in provisions]
    bm25 = Bm25Index(texts, p_ids)

    assert len(bm25) == len(provisions)
    results = bm25.search("bản sao dự phòng", top_k=3)
    assert len(results) > 0
    top_pid = results[0][0]
    assert "Art22" in top_pid


def test_evaluate_system(provisions, tmp_path):
    from evaluation.scripts.metrics.run_recall import evaluate_system
    from retrieval.retriever import Bm25Index
    from main import index_corpus

    tmp_chunks = tmp_path / "chunks.jsonl"
    tmp_index = tmp_path / "faiss.index"
    embedder, faiss_idx, _ = index_corpus(provisions, output_index_path=tmp_index, output_chunks_path=tmp_chunks)
    bm25_idx = Bm25Index([build_index_text(p) for p in provisions], [p.provision_id for p in provisions])
    eval_set = [
        {
            "question": "Quyền tác giả đối với chương trình máy tính",
            "gold_ids": ["67-VBHN-VPQH_Art22_Kh1"],
            "expected_behavior": "answer",
        },
        {
            "question": "tạo bản sao dự phòng chương trình máy tính",
            "gold_ids": ["67-VBHN-VPQH_Art22_Kh1"],
            "expected_behavior": "answer",
        },
    ]
    summary, _ = evaluate_system(eval_set, provisions, embedder, faiss_idx, bm25_idx, k_values=[5])
    recall = summary["modes"]["Hybrid (FAISS+BM25+RRF)"]["recall@5"]
    assert 0.0 <= recall <= 1.0
    assert recall > 0.0


def test_refusal_gate_refuses_when_no_hits():
    decision = decide("query bất kỳ", [])
    assert decision.should_refuse is True


def test_refusal_gate_out_of_scope_keyword():
    decision = decide("Xử phạt vi phạm giao thông xe máy vượt đèn đỏ như thế nào?", [])
    assert decision.should_refuse is True
    assert "ngoài phạm vi" in decision.reason


def test_refusal_gate_can_disable_keyword_layer(provisions, monkeypatch):
    from retrieval.retriever import RetrievalHit
    import generation.llm as llm
    import generation.refusal_gate as rg



    in_scope = next(p for p in provisions if not p.is_distractor)
    hits = [RetrievalHit(provision=in_scope, score=0.8)]
    query = "Quy định về sáng chế trong pháp luật sở hữu trí tuệ là gì?"

    keyword_decision = rg.decide(query, hits)
    semantic_only_decision = rg.decide(query, hits, use_keywords=False)

    assert keyword_decision.should_refuse is True
    assert semantic_only_decision.should_refuse is False


def test_refusal_gate_distractor_ratio(provisions):
    from retrieval.retriever import RetrievalHit

    # Tạo list hits với 80% distractor (4 distractor, 1 in-scope)
    distractors = [p for p in provisions if p.is_distractor][:4]
    in_scope = [p for p in provisions if not p.is_distractor][:1]
    hits = [RetrievalHit(provision=p, score=0.8) for p in distractors + in_scope]
    decision = decide("Quyền tác giả", hits)
    assert decision.should_refuse is True
    assert "dữ liệu nhiễu" in decision.reason





def test_llm_generation_fails_without_fallback(monkeypatch):
    from generation import llm

    monkeypatch.setattr(llm, "get_api_key", lambda: None)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        llm.generate("question", "prompt", [])


def test_llm_runtime_retries_transient_errors_with_backoff(monkeypatch):
    from generation import llm

    attempts = []
    sleeps = []
    responses = [TimeoutError("timeout"), RuntimeError("503 unavailable"),
                 '{"decision":"REFUSE","reason":"insufficient_context","used_documents":[],"answer":""}']

    def call_gemini(prompt, api_key):
        attempts.append(api_key)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(llm, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(llm, "_call_gemini", call_gemini)
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(llm.config, "GEMINI_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(llm.config, "GEMINI_RETRY_BASE_SECONDS", 0.01)

    result = llm.generate("question", "prompt", [])

    assert result["decision"] == "REFUSE"
    assert len(attempts) == 3
    assert sleeps == [0.01, 0.02]


def test_llm_runtime_does_not_retry_non_retryable_errors(monkeypatch):
    from generation import llm

    calls = []
    monkeypatch.setattr(llm, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(llm, "_call_gemini", lambda prompt, api_key: calls.append(1) or (_ for _ in ()).throw(RuntimeError("401 unauthorized")))

    with pytest.raises(RuntimeError, match="không khả dụng"):
        llm.generate("question", "prompt", [])

    assert calls == [1]


def test_ui_uses_safe_message_for_backend_errors():
    from webapp.components import chat

    logged = []
    chat.logger.exception = lambda message: logged.append(message)

    assert chat._safe_user_error() == chat.USER_FACING_ERROR
    assert logged == ["RAG request failed"]
    assert "stack" not in chat.USER_FACING_ERROR.lower()


def test_step_7_analysis_produces_group_ci_latency_and_evidence():
    from evaluation.core.analysis import analyze_records, bootstrap_ci

    records = [
        {"request": {"id": "q1", "group": "Nhóm 1", "expected_behavior": "answer", "gold_ids": ["a"]}, "response": {"status": "success", "retrieved_ids": ["a"], "refused": False, "latency_ms": 10, "retry_count": 0}},
        {"request": {"id": "q2", "group": "Nhóm 4", "expected_behavior": "refuse", "gold_ids": []}, "response": {"status": "success", "retrieved_ids": [], "refused": False, "latency_ms": 30, "retry_count": 1}},
        {"request": {"id": "q3", "group": "Nhóm 5c", "expected_behavior": "refuse", "gold_ids": []}, "response": {"status": "error", "error": "Gemini timeout", "retry_count": 2}},
    ]

    result = analyze_records(records)
    ci = bootstrap_ci([1.0, 0.0, 1.0])

    assert ci["n_resamples"] == 1000
    assert ci["sample_size"] == 3
    assert result["group_retrieval"]["Nhóm 1"]["clause_recall@1"]["point_estimate"] == 1.0
    assert result["group_refusal"]["Nhóm 4"]["false_accept"] == 1
    assert result["latency"]["overall"]["median_ms"] == 20.0
    assert result["latency"]["overall"]["p95_ms"] == 29.0
    assert result["retry"]["observed_retry_count"] == 3
    assert result["error_counts"]["API/Network Error"] == 1


def test_cem_maps_llm_markers_to_candidate_ids(tmp_path):
    from evaluation.scripts.metrics.run_CEM import evaluate_cem

    result_path = tmp_path / "rag.jsonl"
    result_path.write_text(
        json.dumps(
            {
                "request": {"id": "Q1", "gold_ids": ["doc-1", "doc-3"], "expected_behavior": "answer"},
                "response": {
                    "status": "success",
                    "answer": "Theo quy định tại [1] và [2].",
                    "citation_candidates": [
                            {"provision_id": "doc-1", "is_distractor": False},
                            {"provision_id": "doc-2", "is_distractor": True},
                            {"provision_id": "doc-3", "is_distractor": False},
                    ],
                    "cited_documents": [
                        {"provision_id": "doc-1"},
                        {"provision_id": "doc-3"},
                    ],
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = evaluate_cem(result_path)

    assert report["citation_precision"] == 100.0
    assert report["citation_recall"] == 100.0
    assert report["exact_match_rate"] == 100.0


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


def test_pipeline_api_query_in_scope(monkeypatch):
    import pipeline as pipeline_module

    monkeypatch.setattr(
        pipeline_module,
        "generate",
        lambda question, prompt, hits: {
            "answer": "Câu trả lời pháp lý thử nghiệm.",
            "decision": "ANSWER",
            "used_documents": [hits[0].provision.provision_id] if hits else []
        },
    )
    pipeline = RAGPipeline()
    question = "Chương trình máy tính được bảo hộ dưới hình thức nào theo Luật Sở hữu trí tuệ?"
    res = pipeline.query(question)

    assert res.question == question
    assert res.is_refused is False
    assert len(res.answer) > 20
    assert len(res.cited_documents) > 0
    assert res.execution_time_seconds > 0
    assert len(res.retrieval_hits) > 0


def test_pipeline_api_query_refusal_out_of_scope():
    pipeline = RAGPipeline()
    question = "Mức xử phạt vượt đèn đỏ đối với xe máy là bao nhiêu?"
    res = pipeline.query(question)

    assert res.is_refused is True
    assert "ngoài phạm vi" in res.refusal_reason.lower() or "xe máy" in res.refusal_reason.lower()
    assert len(res.cited_documents) == 0


def test_pipeline_api_answer_rag_helper(monkeypatch):
    import pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "generate", lambda question, prompt, hits: {
        "answer": "Câu trả lời.",
        "used_documents": []
    })
    data = answer_rag("Điều 22 Luật Sở hữu trí tuệ quy định gì về bản sao dự phòng phần mềm?")
    assert isinstance(data, dict)
    assert "answer" in data
    assert "cited_documents" in data
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


def test_heldout_questions_are_disjoint_from_dev_set():
    """Held-out refusal questions must not overlap the development benchmark."""
    dev_path = config.DATA_DIR / "evaluation" / "dev_set.json"
    heldout_path = config.DATA_DIR / "evaluation" / "heldout_set.json"
    dev_items = json.loads(dev_path.read_text(encoding="utf-8"))
    heldout_items = json.loads(heldout_path.read_text(encoding="utf-8"))

    dev_ids = {item["id"] for item in dev_items}
    heldout_ids = {item["id"] for item in heldout_items}
    dev_questions = {item["question"].casefold() for item in dev_items}
    heldout_questions = {item["question"].casefold() for item in heldout_items}

    assert len(heldout_items) == 30
    assert dev_ids.isdisjoint(heldout_ids)
    assert dev_questions.isdisjoint(heldout_questions)
    assert {item["group"] for item in heldout_items} == {"Nhóm 4", "Nhóm 5c"}
    assert all(item["expected_behavior"] == "refuse" for item in heldout_items)





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


def test_partial_amendment_updates_only_targeted_provisions():
    from monitoring.crawler import CrawlResult
    from monitoring.effective_checker import apply_crawl_results
    from ingestion.chunker import Provision

    def make_provision(provision_id, article_no, clause_no):
        return Provision(
            provision_id=provision_id,
            law_code="17/2023/ND-CP",
            article_no=article_no,
            clause_no=clause_no,
            title="Điều khoản thử nghiệm",
            text="Nội dung",
            topic="quyen_tac_gia_ctmt",
            is_distractor=False,
            source_url="https://example.invalid",
            status="hieu_luc",
        )

    target = make_provision("17-2023-ND-CP_Art10_Kh1", "10", "1")
    sibling = make_provision("17-2023-ND-CP_Art10_Kh2", "10", "2")
    other_article = make_provision("17-2023-ND-CP_Art11_Kh1", "11", "1")
    snapshot = CrawlResult(
        law_code="17/2023/ND-CP",
        source_url="https://example.invalid",
        crawled_at="2026-10-02T00:00:00+00:00",
        status="con_hieu_luc_mot_phan",
        effective_from="2023-04-26",
        effective_to="2026-04-09",
        replaced_by="134/2026/ND-CP",
        is_mock=False,
        amended_provision_ids=(target.provision_id,),
    )

    updated, _ = apply_crawl_results(snapshot, [target, sibling, other_article])

    assert updated[0].status == "bi_sua_doi"
    assert updated[0].effective_to == "2026-04-09"
    assert updated[0].replaced_by == "134/2026/ND-CP"
    assert updated[1].status == "hieu_luc"
    assert updated[2].status == "hieu_luc"


def test_partial_amendment_without_targets_keeps_provisions_unchanged():
    from monitoring.crawler import CrawlResult
    from monitoring.effective_checker import apply_crawl_results
    from ingestion.chunker import Provision

    provision = Provision(
        provision_id="17-2023-ND-CP_Art10_Kh1",
        law_code="17/2023/ND-CP",
        article_no="10",
        clause_no="1",
        title="Điều khoản thử nghiệm",
        text="Nội dung",
        topic="quyen_tac_gia_ctmt",
        is_distractor=False,
        source_url="https://example.invalid",
        status="hieu_luc",
    )
    snapshot = CrawlResult(
        law_code="17/2023/ND-CP",
        source_url="https://example.invalid",
        crawled_at="2026-10-02T00:00:00+00:00",
        status="con_hieu_luc_mot_phan",
        effective_from="2023-04-26",
        effective_to=None,
        replaced_by=None,
        is_mock=False,
    )

    updated, _ = apply_crawl_results(snapshot, [provision])

    assert updated[0].status == "hieu_luc"
    assert updated[0].effective_to is None
    assert updated[0].replaced_by is None


def test_crawler_failure_returns_unverified_without_mock(monkeypatch):
    from monitoring import crawler

    def fail_open(*args, **kwargs):
        raise TimeoutError("source timeout")

    monkeypatch.setattr(crawler.urllib.request, "urlopen", fail_open)

    result = crawler.fetch_snapshot("67/VBHN-VPQH")

    assert result.status == "unverified"
    assert result.is_mock is False
    assert "TimeoutError" in result.notes


def test_unverified_crawl_does_not_change_existing_status():
    from monitoring.crawler import CrawlResult
    from monitoring.effective_checker import apply_crawl_results
    from ingestion.chunker import Provision

    provision = Provision(
        provision_id="67-VBHN-VPQH_Art22_Kh1",
        law_code="67/VBHN-VPQH",
        article_no="22",
        clause_no="1",
        title="Quyền tác giả",
        text="Nội dung",
        topic="quyen_tac_gia_ctmt",
        is_distractor=False,
        source_url="https://example.invalid",
        status="hieu_luc",
    )
    snapshot = CrawlResult(
        law_code="67/VBHN-VPQH",
        source_url="https://example.invalid",
        crawled_at="2026-10-02T00:00:00+00:00",
        status="unverified",
        effective_from="2026-03-23",
        effective_to=None,
        replaced_by=None,
        is_mock=False,
        notes="source timeout",
    )

    updated, alerts = apply_crawl_results(snapshot, [provision])

    assert updated[0].status == "hieu_luc"
    assert updated[0].effective_to is None
    assert any(alert["alert_type"] == "UNVERIFIED_SOURCE" for alert in alerts)
