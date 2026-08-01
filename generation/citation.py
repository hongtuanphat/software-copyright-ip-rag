"""
generation/citation.py

Xây dựng cấu trúc trích dẫn (citation) trực tiếp từ metadata của các Điều khoản.
Tránh tình trạng hallucination do LLM tự sinh số Điều/Khoản.
"""
from __future__ import annotations

from retrieval.retriever import RetrievalHit


def build_citations(hits: list[RetrievalHit]) -> list[dict]:
    """Tạo danh sách trích dẫn căn cứ pháp lý từ kết quả truy hồi.

    Args:
        hits: Danh sách các RetrievalHit.

    Returns:
        list[dict]: Danh sách dict chứa thông tin trích dẫn pháp lý.
    """
    citations = []
    for h in hits:
        if h.provision.is_distractor:
            continue
        p = h.provision
        citations.append(
            {
                "provision_id": p.provision_id,
                "article_no": p.article_no,
                "title": p.title,
                "law_code": p.law_code,
                "status": p.status,
                "source_url": p.source_url,
                "score": round(h.score, 4),
            }
        )
    return citations
