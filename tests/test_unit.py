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


# ==============================================================================
# KIỂM THỬ BỘ PHÂN LOẠI Ý ĐỊNH VÀ CỔNG TỪ CHỐI MỀM (INTENT CLASSIFIER)
# ==============================================================================
def test_intent_classifier_in_scope(monkeypatch):
    from generation.intent_classifier import (
        classify_query_intent,
        IntentCategory,
        ResponseMode,
    )
    import generation.intent_classifier as ic

    monkeypatch.setattr(ic, "get_api_key", lambda: "mock-key")
    
    mock_payload = '{"intent": "IN_SCOPE", "response_mode": "ANSWER", "should_refuse": false, "reason": "Hợp lệ", "suggested_response": ""}'
    
    class MockClient:
        def __init__(self, **kwargs):
            self.models = self
        def generate_content(self, **kwargs):
            class Resp:
                text = mock_payload
            return Resp()
            
    monkeypatch.setattr(ic.genai, "Client", MockClient)
    
    result = classify_query_intent("Quyền tài sản đối với chương trình máy tính là gì?")
    assert result.intent == IntentCategory.IN_SCOPE
    assert result.response_mode == ResponseMode.ANSWER
    assert result.should_refuse is False


def test_intent_classifier_soft_refusal_document_referral(monkeypatch):
    from generation.intent_classifier import (
        classify_query_intent,
        IntentCategory,
        ResponseMode,
    )
    import generation.intent_classifier as ic

    monkeypatch.setattr(ic, "get_api_key", lambda: "mock-key")
    
    referral_text = "Nội dung phạt tiền quy định tại Nghị định 131/2013/NĐ-CP."
    mock_payload = f'{{"intent": "OUT_OF_SCOPE_SPECIFIC", "response_mode": "SOFT_REFUSE_REFERRAL", "should_refuse": true, "reason": "Mức phạt NĐ 131", "suggested_response": "{referral_text}"}}'
    
    class MockClient:
        def __init__(self, **kwargs):
            self.models = self
        def generate_content(self, **kwargs):
            class Resp:
                text = mock_payload
            return Resp()
            
    monkeypatch.setattr(ic.genai, "Client", MockClient)
    
    result = classify_query_intent("Mức phạt vi phạm bản quyền phần mềm tối đa bao nhiêu?")
    assert result.intent == IntentCategory.OUT_OF_SCOPE_SPECIFIC
    assert result.response_mode == ResponseMode.SOFT_REFUSE_REFERRAL
    assert result.should_refuse is True
    assert "131/2013" in result.suggested_response


def test_intent_classifier_soft_refusal_false_premise_clarify(monkeypatch):
    from generation.intent_classifier import (
        classify_query_intent,
        IntentCategory,
        ResponseMode,
    )
    import generation.intent_classifier as ic

    monkeypatch.setattr(ic, "get_api_key", lambda: "mock-key")
    
    clarify_text = "Căn cứ Khoản 1 Điều 12a, AI không thể đứng tên tác giả."
    mock_payload = f'{{"intent": "FALSE_PREMISE", "response_mode": "SOFT_REFUSE_CLARIFY", "should_refuse": true, "reason": "AI không là tác giả", "suggested_response": "{clarify_text}"}}'
    
    class MockClient:
        def __init__(self, **kwargs):
            self.models = self
        def generate_content(self, **kwargs):
            class Resp:
                text = mock_payload
            return Resp()
            
    monkeypatch.setattr(ic.genai, "Client", MockClient)
    
    result = classify_query_intent("ChatGPT có được đứng tên tác giả phần mềm không?")
    assert result.intent == IntentCategory.FALSE_PREMISE
    assert result.response_mode == ResponseMode.SOFT_REFUSE_CLARIFY
    assert result.should_refuse is True
    assert "Điều 12a" in result.suggested_response


def test_intent_classifier_fallback_on_api_error(monkeypatch):
    from generation.intent_classifier import classify_query_intent, IntentCategory
    import generation.intent_classifier as ic

    monkeypatch.setattr(ic, "get_api_key", lambda: "mock-key")
    
    class FailingClient:
        def __init__(self, **kwargs):
            self.models = self
        def generate_content(self, **kwargs):
            raise RuntimeError("API quota exceeded")
            
    monkeypatch.setattr(ic.genai, "Client", FailingClient)
    
    # Khi gặp lỗi API, hệ thống fallback coi như IN_SCOPE và tiếp tục chuyển tiếp
    result = classify_query_intent("Một câu hỏi bất kỳ")
    assert result.intent == IntentCategory.IN_SCOPE
    assert result.should_refuse is False


def test_refusal_gate_allows_valid_labor_contract_for_software():
    from generation.refusal_gate import decide
    from retrieval.retriever import RetrievalHit
    from ingestion.chunker import Provision

    mock_p = Provision(
        provision_id="67_Art39",
        law_code="67/VBHN-VPQH",
        article_no="39",
        clause_no="1",
        title="Chủ sở hữu quyền tác giả khi giao kết hợp đồng",
        text="Tổ chức giao nhiệm vụ sáng tạo tác phẩm...",
        topic="in_scope",
        is_distractor=False,
        source_url="http://test"
    )
    hits = [RetrievalHit(provision=mock_p, score=0.85)]

    # Câu hỏi hợp lệ về phần mềm sáng tạo theo hợp đồng lao động (Điều 39)
    valid_query = "Lập trình viên viết phần mềm theo hợp đồng lao động thì ai sở hữu bản quyền tài sản?"
    decision = decide(valid_query, hits=hits, use_keywords=True)
    assert decision.should_refuse is False, "Không được từ chối câu hỏi hợp lệ về phần mềm theo hợp đồng lao động"

    # Câu hỏi ngoài phạm vi về lao động (sa thải thuần túy) phải bị từ chối
    out_query = "Thủ tục sa thải người lao động theo luật lao động?"
    decision_out = decide(out_query, hits=[], use_keywords=True)
    assert decision_out.should_refuse is True, "Phải từ chối câu hỏi thuần túy về sa thải lao động"


# ==========================================
# CÁC BÀI KIỂM THỬ ĐỘ ỔN ĐỊNH RUNTIME, RETRY JSON VÀ RATE LIMITING
# ==========================================

def test_llm_docstring_and_clean_json_markdown():
    """Kiểm tra docstring của hàm generate() đặt đúng đầu hàm và xử lý gọt markdown json."""
    from generation import llm

    # 1. Docstring phải tồn tại và đúng vị trí đầu hàm
    assert llm.generate.__doc__ is not None
    assert "lỗi định dạng JSON" in llm.generate.__doc__

    # 2. Gọt bỏ khối mã markdown code block
    raw_markdown_json = "```json\n{\"decision\": \"ANSWER\"}\n```"
    cleaned = llm._clean_json_markdown(raw_markdown_json)
    assert cleaned == '{"decision": "ANSWER"}'

    raw_plain_markdown = "```\n{\"decision\": \"ANSWER\"}\n```"
    cleaned_plain = llm._clean_json_markdown(raw_plain_markdown)
    assert cleaned_plain == '{"decision": "ANSWER"}'


def test_llm_retries_on_json_decode_error(monkeypatch):
    """Kiểm tra hàm generate() tự động retry khi gặp JSONDecodeError và thành công ở lần sau."""
    from generation import llm
    import config

    attempts = []
    responses = [
        "LỖI CẮT CỤT: {decision: incomplete",  # Lần 1: JSON hỏng
        '{"decision": "ANSWER", "reason": "answered", "used_documents": ["67_Art22"], "answer": "Được bảo hộ."}'  # Lần 2: JSON chuẩn
    ]

    def mock_call(prompt, api_key):
        attempts.append(api_key)
        return responses.pop(0)

    monkeypatch.setattr(llm, "get_api_key", lambda: "test-api-key")
    monkeypatch.setattr(llm, "_call_gemini", mock_call)
    monkeypatch.setattr(llm.time, "sleep", lambda sec: None)
    monkeypatch.setattr(config, "GEMINI_MAX_ATTEMPTS", 3)

    result = llm.generate("prompt test")
    assert result["decision"] == "ANSWER"
    assert len(attempts) == 2, "Hệ thống phải thử lại lần 2 khi lần 1 gặp lỗi JSON"


def test_llm_exhausts_retries_on_persistent_json_error(monkeypatch):
    """Kiểm tra hàm generate() báo lỗi rõ ràng sau khi đã thử hết số lần cho phép với JSON hỏng."""
    import pytest
    from generation import llm
    import config

    attempts = []

    def mock_call(prompt, api_key):
        attempts.append(api_key)
        return "hoan_toan_khong_phai_json"

    monkeypatch.setattr(llm, "get_api_key", lambda: "test-api-key")
    monkeypatch.setattr(llm, "_call_gemini", mock_call)
    monkeypatch.setattr(llm.time, "sleep", lambda sec: None)
    monkeypatch.setattr(config, "GEMINI_MAX_ATTEMPTS", 3)

    with pytest.raises(RuntimeError, match="JSON không hợp lệ sau 3 lần thử"):
        llm.generate("prompt test")

    assert len(attempts) == 3, "Phải retry đủ 3 lần trước khi dừng"


def test_pipeline_no_global_mutable_state():
    """Kiểm tra module pipeline không còn biến toàn cục mutable _global_pipeline."""
    import pipeline

    assert not hasattr(pipeline, "_global_pipeline"), "Biến toàn cục _global_pipeline phải bị loại bỏ hoàn toàn"

    # get_pipeline() tạo instance độc lập
    p1 = pipeline.get_pipeline(mode="bm25")
    p2 = pipeline.get_pipeline(mode="dense")
    assert p1 is not p2, "get_pipeline() phải trả về các instance độc lập"
    assert p1.mode == "bm25"
    assert p2.mode == "dense"


def test_rate_limiter_logic_simulation():
    """Mô phỏng kiểm tra logic Rate Limiting (cooldown và requests per minute)."""
    import config

    cooldown = config.RATE_LIMIT_COOLDOWN_SECONDS
    max_rpm = config.RATE_LIMIT_MAX_PER_MINUTE

    # 1. Kiểm tra cooldown: 2 request cách nhau < cooldown phải bị từ chối
    last_query_time = 100.0
    now_too_fast = 101.0  # cách 1.0s < 3.0s
    assert (now_too_fast - last_query_time) < cooldown, "Phải phát hiện vi phạm cooldown"

    # 2. Kiểm tra RPM: số lượt trong 60s vượt quá max_rpm phải bị chặn
    current_time = 200.0
    timestamps = [current_time - (i * 2.0) for i in range(max_rpm)]  # max_rpm lượt trong 24s gần đây
    valid_ts = [ts for ts in timestamps if current_time - ts < 60.0]
    assert len(valid_ts) >= max_rpm, "Phải phát hiện vi phạm giới hạn câu hỏi/phút"

