"""pipeline.py

Backend Service API đóng gói toàn bộ luồng RAG cho hệ thống:
Nạp dữ liệu -> Nhận câu hỏi -> Truy hồi FAISS -> Cổng từ chối (Refusal Gate) -> Sinh câu trả lời qua Gemini -> Đính kèm trích dẫn.
Phục vụ kết nối trực tiếp với giao diện Web Streamlit (webapp/app.py).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

import config
from generation.citation import build_citations
from generation.llm import generate
from generation.prompt_builder import build_prompt
from generation.refusal_gate import decide
from ingestion.chunker import Provision
from retrieval.embedder import get_embedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.retriever import RetrievalHit, retrieve


@dataclass
class RAGResponse:
    """Cấu trúc dữ liệu kết quả trả về từ RAG Pipeline cho Web UI hoặc API."""

    question: str
    answer: str
    is_refused: bool
    refusal_reason: str
    citations: list[dict[str, Any]]
    retrieved_provisions: list[dict[str, Any]]
    execution_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Chuyển kết quả sang dạng dictionary để giao diện dễ sử dụng."""
        return asdict(self)


class RAGPipeline:
    """Lớp xử lý chính của Backend RAG, duy trì bộ nhớ đệm và chỉ mục trong RAM."""

    def __init__(
        self,
        chunks_path: Path = config.CHUNKS_PATH,
        faiss_index_path: Path = config.FAISS_INDEX_PATH,
    ) -> None:
        self.chunks_path = chunks_path
        self.faiss_index_path = faiss_index_path

        # 1. Nạp danh sách Provision từ chunks.jsonl
        self.provisions = self._load_provisions()

        # 2. Khởi tạo mô hình Embedder
        self.embedder = get_embedder()

        # 3. Nạp chỉ mục FAISS Index đã lưu sẵn
        self.faiss_index = self._load_faiss_index()

    def _load_provisions(self) -> list[Provision]:
        """Đọc danh sách các đoạn luật đã được tiền xử lý và gắn metadata."""
        if not self.chunks_path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy file chunks tại {self.chunks_path}. "
                "Vui lòng chạy 'python -X utf8 main.py' để khởi tạo dữ liệu trước."
            )
        provisions = []
        with self.chunks_path.open("r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    data = json.loads(line_str)
                    provisions.append(Provision(**data))
        return provisions

    def _load_faiss_index(self) -> FaissFlatIndex:
        """Nạp chỉ mục vector từ đĩa, nếu chưa có thì tự động tạo mới."""
        if not self.faiss_index_path.exists():
            texts = [p.text for p in self.provisions]
            vectors = self.embedder.encode(texts)
            idx = FaissFlatIndex(vectors.shape[1])
            idx.add(np.asarray(vectors), [p.provision_id for p in self.provisions])
            idx.save(self.faiss_index_path)
            return idx
        return FaissFlatIndex.load(self.faiss_index_path)

    def query(self, question: str, top_k: int = config.TOP_K) -> RAGResponse:
        """Xử lý câu hỏi của người dùng từ đầu đến cuối và trả về đối tượng RAGResponse."""
        start_time = time.time()
        q_clean = question.strip()

        # 1. Truy hồi các điều khoản liên quan nhất
        hits: list[RetrievalHit] = retrieve(
            query=q_clean,
            provisions=self.provisions,
            embedder=self.embedder,
            faiss_index=self.faiss_index,
            top_k=top_k,
        )

        # 2. Đánh giá câu hỏi qua cổng từ chối (Refusal Gate)
        decision = decide(q_clean, hits)

        if decision.should_refuse:
            latency = round(time.time() - start_time, 3)
            return RAGResponse(
                question=q_clean,
                answer=(
                    "Xin lỗi, câu hỏi của bạn nằm ngoài phạm vi tư vấn về Quyền tác giả đối với "
                    "chương trình máy tính theo Luật Sở hữu trí tuệ hoặc không đủ tài liệu căn cứ để trả lời."
                ),
                is_refused=True,
                refusal_reason=decision.reason,
                citations=[],
                retrieved_provisions=[
                    {
                        "article_no": h.provision.article_no,
                        "title": h.provision.title,
                        "score": round(float(h.score), 4),
                        "is_distractor": h.provision.is_distractor,
                    }
                    for h in hits
                ],
                execution_time_seconds=latency,
            )

        # 3. Xây dựng prompt có ngữ cảnh và trích dẫn chuẩn
        prompt = build_prompt(q_clean, hits)

        # 4. Sinh câu trả lời qua Gemini LLM (hoặc extractive fallback nếu lỗi mạng)
        answer = generate(q_clean, prompt, hits)

        # 5. Xây dựng danh sách trích dẫn căn cứ pháp lý
        citations = build_citations(hits)

        latency = round(time.time() - start_time, 3)
        return RAGResponse(
            question=q_clean,
            answer=answer,
            is_refused=False,
            refusal_reason=decision.reason,
            citations=citations,
            retrieved_provisions=[
                {
                    "article_no": h.provision.article_no,
                    "title": h.provision.title,
                    "score": round(float(h.score), 4),
                    "is_distractor": h.provision.is_distractor,
                }
                for h in hits
            ],
            execution_time_seconds=latency,
        )


# Biến toàn cục nạp sẵn pipeline vào RAM để không phải nạp lại mô hình nhiều lần
_global_pipeline: Optional[RAGPipeline] = None


def answer_rag(question: str) -> dict[str, Any]:
    """Hàm helper tiện lợi dành cho Streamlit UI hoặc REST API."""
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = RAGPipeline()
    return _global_pipeline.query(question).to_dict()
