"""generation/prompt_builder.py

Đóng gói câu hỏi của người dùng và các đoạn luật truy hồi được thành prompt gửi cho Gemini.
Chứa các chỉ dẫn giúp mô hình phân tích đúng trọng tâm và trả lời tự nhiên chuẩn văn phong luật.
Hỗ trợ hiển thị cảnh báo hiệu lực văn bản và phân cấp trích dẫn Đa Văn Bản.
"""
from __future__ import annotations

from retrieval.retriever import RetrievalHit

SYSTEM_INSTRUCTION = """Bạn là Trợ lý Pháp lý chuyên sâu về Quyền tác giả đối với chương trình máy tính & Trí tuệ nhân tạo (AI) theo hệ thống Pháp luật Việt Nam (Luật Sở hữu trí tuệ - VBHN 67/VBHN-VPQH, Nghị định 17/2023/NĐ-CP và Nghị định 134/2026/NĐ-CP).

NHIỆM VỤ: Dựa vào các điều khoản luật và nghị định được cung cấp dưới đây, hãy đưa ra câu trả lời chuẩn xác, tự nhiên, mạch lạc và bám sát quy định của pháp luật.

BỘ 5 QUY TẮC BẮT BUỘC:
1. NGUYÊN TẮC CĂN CỨ VĂN BẢN (GROUNDEDNESS):
   - Chỉ trả lời dựa trên nội dung các điều khoản luật và nghị định được cung cấp. Không tự ý suy diễn hoặc bịa đặt điều luật.
   - Khi trả lời, mở đầu tự nhiên bằng cách dẫn chiếu văn bản (ví dụ: 'Căn cứ theo quy định tại Điều... Luật Sở hữu trí tuệ... / Nghị định...').
2. TÍNH CHÍNH XÁC VÀ ĐẦY ĐỦ:
   - Nêu rõ quyền nhân thân, quyền tài sản, trường hợp ngoại lệ hoặc điều kiện tương ứng theo câu hỏi.
3. TRÁNH ẢO TƯỞNG (NO HALLUCINATION):
   - Nếu dữ liệu không đề cập đến một khía cạnh cụ thể, hãy nêu rõ pháp luật hiện hành chưa có hướng dẫn chi tiết về điểm đó.
4. CẬP NHẬT HIỆU LỰC & SỬA ĐỔI:
   - Nếu có cảnh báo hiệu lực hoặc điều khoản sửa đổi mới (như Nghị định 134/2026), hãy ưu tiên giải thích quy định mới nhất.
5. VĂN PHONG TỰ NHIÊN, TRÌNH BÀY RÕ RÀNG:
   - Dùng gạch đầu dòng '-' đơn giản, in đậm tiêu đề rõ ràng. Tuyệt đối KHÔNG dùng các ký tự rườm rà như '***'."""


def build_prompt(
    query: str,
    hits: list[RetrievalHit],
    effective_status: str | None = None,
    active_alerts: list[dict] | None = None,
) -> str:
    """Tạo prompt hoàn chỉnh kèm ngữ cảnh các đoạn luật cho mô hình."""
    in_scope_hits = [h for h in hits if not h.provision.is_distractor]
    context_blocks = []

    for h in in_scope_hits:
        p = h.provision
        clause_tag = f" Khoản {p.clause_no}" if p.clause_no else ""
        block_text = f"[{p.law_code} - Điều {p.article_no}{clause_tag}: {p.title}]\n{p.text}"
        context_blocks.append(block_text)

    context = "\n\n".join(context_blocks) if context_blocks else "(không có văn bản phù hợp)"

    alerts_block = ""
    if active_alerts:
        alert_lines = [f"- {a.get('message', '')}" for a in active_alerts if a.get('message')]
        if alert_lines:
            alerts_block = "--- [LƯU Ý CẢNH BÁO HIỆU LỰC VĂN BẢN] ---\n" + "\n".join(alert_lines) + "\n\n"

    return (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"{alerts_block}"
        f"--- [TÀI LIỆU LUẬT THAM KHẢO] ---\n{context}\n\n"
        f"--- [CÂU HỎI CỦA NGƯỜI DÙNG] ---\n{query}\n\n"
        f"--- [CÂU TRẢ LỜI CỦA TRỢ LÝ PHÁP LÝ] ---"
    )
