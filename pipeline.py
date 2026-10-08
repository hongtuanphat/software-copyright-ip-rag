"""pipeline.py

Module đóng gói toàn bộ quy trình xử lý câu hỏi RAG:
Nạp dữ liệu -> Nhận câu hỏi -> Tìm kiếm kết hợp (FAISS + BM25 + RRF) -> Bộ lọc từ chối -> Gọi Gemini sinh câu trả lời -> Gắn trích dẫn và cảnh báo hiệu lực.
Cung cấp hàm answer_rag() để nối trực tiếp với giao diện Web Streamlit.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


import config
from generation.llm import generate
from generation.prompt_builder import build_prompt
from generation.refusal_gate import decide, check_metric_gate
from generation.intent_classifier import classify_query_intent
from generation.citation import build_citations
from ingestion.chunker import Provision
from ingestion.utils import build_index_text
from monitoring.effective_checker import get_active_alerts
from retrieval.bm25_index import Bm25Index
from retrieval.embedder import get_embedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import retrieve, retrieve_bm25, retrieve_hybrid


@dataclass
class RAGResponse:
    """Kết quả trả về cho giao diện Web hoặc API."""

    question: str
    answer: str
    raw_answer: str = ""
    should_refuse: bool = False
    refusal_reason: str = ""
    retrieval_hits: list[dict[str, Any]] = field(default_factory=list)
    cited_documents: list[dict[str, Any]] = field(default_factory=list)
    execution_time_ms: float = 0.0
    active_alerts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_refused(self) -> bool:
        return self.should_refuse

    @property
    def execution_time_seconds(self) -> float:
        return self.execution_time_ms / 1000.0 if self.execution_time_ms else 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_refused"] = self.should_refuse
        d["execution_time_seconds"] = self.execution_time_seconds
        return d


class RAGPipeline:
    """Lớp điều phối chính cho hệ thống RAG."""

    def __init__(
        self,
        mode: str = config.RETRIEVAL_MODE,
        enable_entity: bool = True,
        use_keywords: bool = True,
        use_semantic: bool = True,
    ):
        self.mode = mode
        self.enable_entity = enable_entity
        self.use_keywords = use_keywords
        self.use_semantic = use_semantic
        self.provisions: list[Provision] = []
        self.embedder: Any = None
        self.faiss_index: Optional[FaissFlatIndex] = None
        self.bm25_index: Optional[Bm25Index] = None
        self._is_ready = False
        self._initialize()

    def _initialize(self) -> None:
        """Nạp dữ liệu chunks, mô hình nhúng và các chỉ mục tìm kiếm."""
        if not config.CHUNKS_PATH.exists():
            return

        # 1. Đọc các đoạn luật từ chunks.jsonl
        with open(config.CHUNKS_PATH, "r", encoding="utf-8") as f:
            self.provisions = [
                Provision(**json.loads(line))
                for line in f
                if line.strip()
            ]

        # 2. Khởi tạo mô hình nhúng và chỉ mục FAISS
        self.embedder = get_embedder()
        if config.FAISS_INDEX_PATH.exists():
            self.faiss_index = FaissFlatIndex.load(
                config.FAISS_INDEX_PATH,
                expected_dim=config.EMBEDDING_DIM,
                expected_ids=[p.provision_id for p in self.provisions],
                expected_model_name=getattr(self.embedder, "model_name", config.EMBEDDING_MODEL_NAME),
            )
        else:
            texts = [build_index_text(p) for p in self.provisions]
            vecs = self.embedder.encode(texts)
            dim = int(vecs.shape[1]) if hasattr(vecs, "shape") else config.EMBEDDING_DIM
            self.faiss_index = FaissFlatIndex(dim=dim)
            pids = [p.provision_id for p in self.provisions]
            self.faiss_index.add(vecs, pids)

        # 3. Tạo chỉ mục từ khóa BM25
        texts = [build_index_text(p) for p in self.provisions]
        pids = [p.provision_id for p in self.provisions]
        self.bm25_index = Bm25Index(texts, pids)

        self._is_ready = True

    def query(self, question: str, top_k: int = config.TOP_K) -> RAGResponse:
        """Xử lý một câu hỏi từ người dùng từ đầu đến cuối."""
        start_time = time.time()

        if not self._is_ready or not self.provisions:
            self._initialize()
            if not self._is_ready:
                return RAGResponse(
                    question=question,
                    answer="Hệ thống chưa nạp được dữ liệu luật.",
                    should_refuse=True,
                    refusal_reason="Dữ liệu chưa sẵn sàng.",
                )

        # 1. Cổng từ chối sớm (Pre-retrieval Gate) tích hợp phân loại ý định ngữ nghĩa và từ khóa vĩ mô
        early_decision = decide(
            question,
            hits=None,
            use_keywords=self.use_keywords,
            use_semantic=self.use_semantic,
        )
        if early_decision.should_refuse:
            elapsed_ms = (time.time() - start_time) * 1000.0
            active_alerts = get_active_alerts()
            return RAGResponse(
                question=question,
                answer=early_decision.suggested_response or early_decision.reason,
                should_refuse=True,
                refusal_reason=early_decision.reason,
                execution_time_ms=elapsed_ms,
                active_alerts=active_alerts,
            )

        if self.mode == "hybrid" and self.bm25_index is not None and self.faiss_index is not None:
            hits = retrieve_hybrid(
                question,
                self.provisions,
                self.embedder,
                self.faiss_index,
                self.bm25_index,
                top_k=top_k,
                enable_entity=self.enable_entity,
            )
        elif self.mode == "bm25" and self.bm25_index is not None:
            hits = retrieve_bm25(question, self.provisions, self.bm25_index, top_k=top_k)
        elif self.mode == "dense" and self.faiss_index is not None:
            hits = retrieve(question, self.provisions, self.embedder, self.faiss_index, top_k=top_k)
        else:
            raise ValueError(f"Chế độ tìm kiếm không hợp lệ hoặc chỉ mục bị thiếu: mode='{self.mode}'")

        # 3. Kiểm tra độ tin cậy kết quả truy hồi qua cổng số học (Metric Gate)
        decision = check_metric_gate(hits)
        active_alerts = get_active_alerts()

        # Đóng gói danh sách kết quả tìm được
        retrieval_hits = [
            {
                "provision_id": h.provision.provision_id,
                "law_code": h.provision.law_code,
                "article_no": h.provision.article_no,
                "clause_no": h.provision.clause_no,
                "title": h.provision.title,
                "text": h.provision.text,
                "topic": h.provision.topic,
                "status": h.provision.status,
                "effective_from": h.provision.effective_from,
                "effective_to": h.provision.effective_to,
                "replaced_by": h.provision.replaced_by,
                "score": h.score,
                "is_distractor": h.provision.is_distractor,
            }
            for h in hits
        ]

        # Nếu câu hỏi bị từ chối
        if decision.should_refuse:
            elapsed_ms = (time.time() - start_time) * 1000.0
            refusal_text = (
                "Xin lỗi, tôi không thể trả lời câu hỏi này do nằm ngoài phạm vi chuyên môn "
                f"về bản quyền phần mềm hoặc không đủ căn cứ pháp lý tin cậy.\n"
                f"Lý do: {decision.reason}"
            )
            return RAGResponse(
                question=question,
                answer=refusal_text,
                should_refuse=True,
                refusal_reason=decision.reason,
                retrieval_hits=retrieval_hits,
                execution_time_ms=elapsed_ms,
                active_alerts=active_alerts,
            )

        # 3. Tạo lời nhắc (prompt) và gọi mô hình sinh câu trả lời (định dạng JSON)
        prompt = build_prompt(question, hits, active_alerts=active_alerts)
        llm_response = generate(question, prompt, hits)
        
        decision_str = str(llm_response.get("decision", "")).strip().upper()
        reason_str = str(llm_response.get("reason", "")).strip()
        answer_text = llm_response.get("answer", "")
        
        cited_documents = build_citations(hits)
        
        # Chỉ lấy những doc mà LLM thực sự dùng
        used_ids = llm_response.get("used_documents", [])
        if used_ids and decision_str != "REFUSE":
            cited_documents = [doc for doc in cited_documents if doc["provision_id"] in used_ids]
        else:
            cited_documents = []
        
        # Nếu LLM phân tích ngữ cảnh và quyết định từ chối (Dynamic Refusal)
        if decision_str == "REFUSE":
            elapsed_ms = (time.time() - start_time) * 1000.0
            return RAGResponse(
                question=question,
                answer=answer_text if answer_text else "Xin lỗi, tôi không đủ thông tin pháp lý để trả lời câu hỏi này.",
                raw_answer=llm_response.get("answer", ""),
                should_refuse=True,
                refusal_reason=reason_str if reason_str else "LLM quyết định từ chối dựa trên phân tích ngữ cảnh và yêu cầu.",
                retrieval_hits=retrieval_hits,
                cited_documents=[],
                execution_time_ms=elapsed_ms,
                active_alerts=active_alerts,
            )

        elapsed_ms = (time.time() - start_time) * 1000.0

        return RAGResponse(
            question=question,
            answer=answer_text,
            raw_answer=llm_response.get("answer", ""),
            should_refuse=False,
            refusal_reason=reason_str,
            retrieval_hits=retrieval_hits,
            cited_documents=cited_documents,
            execution_time_ms=elapsed_ms,
            active_alerts=active_alerts,
        )


def get_pipeline(
    mode: str = config.RETRIEVAL_MODE,
    enable_entity: bool = True,
    use_keywords: bool = True,
    use_semantic: bool = True,
) -> RAGPipeline:
    """Tạo một instance RAGPipeline theo cấu hình, đảm bảo tính stateless và thread-safe giữa các yêu cầu."""
    return RAGPipeline(
        mode=mode,
        enable_entity=enable_entity,
        use_keywords=use_keywords,
        use_semantic=use_semantic,
    )


def answer_rag(
    question: str,
    top_k: int = config.TOP_K,
    pipeline: Optional[RAGPipeline] = None,
) -> dict[str, Any]:
    """Hàm tiện ích gọi nhanh từ giao diện Web Streamlit hoặc kịch bản kiểm thử."""
    active_pipeline = pipeline if pipeline is not None else get_pipeline()
    response = active_pipeline.query(question, top_k=top_k)
    return response.to_dict()
