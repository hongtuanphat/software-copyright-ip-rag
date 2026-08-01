"""
generation/prompt_builder.py

Xây dựng prompt cho mô hình sinh phản hồi (LLM).
Đảm bảo loại bỏ hoàn toàn các đoạn trích nhiễu (distractor) khỏi ngữ cảnh (context).
"""
from __future__ import annotations

from retrieval.retriever import RetrievalHit

SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý tra cứu pháp luật về quyền tác giả đối với chương trình "
    "máy tính theo Luật Sở hữu trí tuệ Việt Nam. CHỈ được trả lời dựa trên "
    "các đoạn trích dẫn được cung cấp trong CONTEXT dưới đây. KHÔNG được tự "
    "suy đoán, KHÔNG được tự bịa số Điều/Khoản. Nếu CONTEXT không đủ căn cứ "
    "để trả lời, hãy nói rõ là không có đủ căn cứ."
)


def build_prompt(query: str, hits: list[RetrievalHit]) -> str:
    """Tạo prompt chuỗi văn bản cho LLM từ câu hỏi và danh sách trích dẫn.

    Args:
        query: Câu hỏi cần xử lý.
        hits: Kết quả truy hồi đã được lọc.

    Returns:
        str: Chuỗi prompt hoàn chỉnh cho mô hình LLM.
    """
    in_scope_hits = [h for h in hits if not h.provision.is_distractor]
    context_blocks = []
    for h in in_scope_hits:
        p = h.provision
        context_blocks.append(
            f"[Điều {p.article_no} — {p.title}]\n{p.text}"
        )
    context = "\n\n".join(context_blocks) if context_blocks else "(không có)"

    return (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"CÂU HỎI: {query}\n\n"
        "Trả lời ngắn gọn, chính xác, và liệt kê các Điều khoản tham chiếu ở cuối."
    )
