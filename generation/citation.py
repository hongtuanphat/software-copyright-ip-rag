"""generation/citation.py

Xây dựng cấu trúc trích dẫn (citation) trực tiếp từ metadata của các Điều khoản.
Tránh tình trạng hallucination do LLM tự sinh số Điều/Khoản.
"""
from __future__ import annotations

from retrieval.retriever import RetrievalHit

# Bảng ánh xạ mã văn bản → tên đầy đủ để hiển thị trong UI
_LAW_NAME_MAP: dict[str, str] = {
    "67/VBHN-VPQH": "Luật Sở hữu trí tuệ",
    "17/2023/ND-CP": "Nghị định 17/2023/NĐ-CP",
    "17/2023/NĐ-CP": "Nghị định 17/2023/NĐ-CP",
    "134/2026/ND-CP": "Nghị định 134/2026/NĐ-CP",
    "134/2026/NĐ-CP": "Nghị định 134/2026/NĐ-CP",
}


def _resolve_law_name(law_code: str) -> str:
    """Trả về tên văn bản đầy đủ từ mã văn bản, hoặc fallback về mã nếu không tìm thấy."""
    if not law_code:
        return "Văn bản pháp luật"
    return _LAW_NAME_MAP.get(law_code.strip(), f"Văn bản {law_code}")


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
                "clause_no": p.clause_no,
                "title": p.title,
                "law_code": p.law_code,
                "law_name": getattr(p, "law_name", None) or _resolve_law_name(p.law_code),
                "status": p.status,
                "source_url": p.source_url,
                "text": p.text,
                "score": round(h.score, 4),
            }
        )
    return citations
