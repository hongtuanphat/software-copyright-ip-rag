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

import numpy as np

import config
from generation.citation import build_citations
from generation.llm import generate
from generation.prompt_builder import build_prompt
from generation.refusal_gate import decide
from ingestion.chunker import Provision
from monitoring.effective_checker import get_active_alerts
from retrieval.bm25_index import Bm25Index
from retrieval.embedder import get_embedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import RetrievalHit, retrieve, retrieve_bm25, retrieve_hybrid


@dataclass
class RAGResponse:
    """Kết quả trả về cho giao diện Web hoặc API."""

    question: str
    answer: str
    should_refuse: bool = False
    refusal_reason: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    retrieval_hits: list[dict[str, Any]] = field(default_factory=list)
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

    def __init__(self, mode: str = config.RETRIEVAL_MODE):
        self.mode = mode
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
            self.faiss_index = FaissFlatIndex.load(config.FAISS_INDEX_PATH)
        else:
            texts = [p.text for p in self.provisions]
            vecs = self.embedder.encode(texts)
            dim = int(vecs.shape[1]) if hasattr(vecs, "shape") else config.EMBEDDING_DIM
            self.faiss_index = FaissFlatIndex(dim=dim)
            pids = [p.provision_id for p in self.provisions]
            self.faiss_index.add(vecs, pids)

        # 3. Tạo chỉ mục từ khóa BM25
        texts = [p.text for p in self.provisions]
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

        # 1. Tìm kiếm đoạn luật liên quan theo chế độ được chọn
        if self.mode == "hybrid" and self.bm25_index is not None and self.faiss_index is not None:
            hits = retrieve_hybrid(
                question,
                self.provisions,
                self.embedder,
                self.faiss_index,
                self.bm25_index,
                top_k=top_k,
            )
        elif self.mode == "bm25" and self.bm25_index is not None:
            hits = retrieve_bm25(question, self.provisions, self.bm25_index, top_k=top_k)
        elif self.faiss_index is not None:
            hits = retrieve(question, self.provisions, self.embedder, self.faiss_index, top_k=top_k)
        else:
            hits = []

        # 2. Kiểm tra câu hỏi qua bộ lọc từ chối
        decision = decide(question, hits)
        active_alerts = get_active_alerts()

        # Đóng gói danh sách kết quả tìm được
        retrieval_hits_data = [
            {
                "provision_id": h.provision.provision_id,
                "article_no": h.provision.article_no,
                "clause_no": h.provision.clause_no,
                "title": h.provision.title,
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
                retrieval_hits=retrieval_hits_data,
                execution_time_ms=elapsed_ms,
                active_alerts=active_alerts,
            )

        # 3. Tạo prompt và gọi Gemini sinh câu trả lời
        prompt = build_prompt(question, hits)
        answer = generate(question, prompt, hits)

        # 4. Tạo danh sách trích dẫn điều luật
        citations = build_citations(hits)
        elapsed_ms = (time.time() - start_time) * 1000.0

        return RAGResponse(
            question=question,
            answer=answer,
            should_refuse=False,
            refusal_reason="",
            citations=citations,
            retrieval_hits=retrieval_hits_data,
            execution_time_ms=elapsed_ms,
            active_alerts=active_alerts,
        )


# Biến toàn cục để dùng chung một instance pipeline duy nhất
_global_pipeline: Optional[RAGPipeline] = None


def get_pipeline(mode: str = config.RETRIEVAL_MODE) -> RAGPipeline:
    """Lấy hoặc khởi tạo instance pipeline dùng chung."""
    global _global_pipeline
    if _global_pipeline is None or _global_pipeline.mode != mode:
        _global_pipeline = RAGPipeline(mode=mode)
    return _global_pipeline


def answer_rag(question: str, top_k: int = config.TOP_K) -> dict[str, Any]:
    """Hàm tiện ích gọi nhanh từ giao diện Web Streamlit."""
    pipeline = get_pipeline()
    response = pipeline.query(question, top_k=top_k)
    return response.to_dict()
