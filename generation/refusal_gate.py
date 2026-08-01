"""
generation/refusal_gate.py

Module đánh giá độ tin cậy và quyết định từ chối (Refusal Gate) cho câu hỏi đầu vào.
Kế thừa cơ chế đa tín hiệu: điểm tương đồng vector, tỷ lệ dữ liệu nhiễu (distractor),
và danh sách từ khóa ngoài phạm vi.
"""
from __future__ import annotations

from dataclasses import dataclass
from retrieval.retriever import RetrievalHit

MIN_SCORE_TIN_CAY = 0.35
MAX_DISTRACTOR_RATIO = 0.6

OUT_OF_SCOPE_KEYWORDS = [
    "xe máy",
    "vượt đèn đỏ",
    "thuế giá trị gia tăng",
    "luật lao động",
    "bảo hiểm xã hội",
]


@dataclass
class RefusalDecision:
    should_refuse: bool
    reason: str


def decide(query: str, hits: list[RetrievalHit]) -> RefusalDecision:
    """Đánh giá và đưa ra quyết định có từ chối trả lời câu hỏi hay không.

    Args:
        query: Câu hỏi của người dùng.
        hits: Danh sách kết quả truy hồi (RetrievalHit).

    Returns:
        RefusalDecision: Kết quả chứa trạng thái should_refuse và lý do.
    """
    query_low = query.lower()
    for kw in OUT_OF_SCOPE_KEYWORDS:
        if kw in query_low:
            return RefusalDecision(
                True, f"Câu hỏi chứa chủ đề ngoài phạm vi Luật Sở hữu trí tuệ ('{kw}')."
            )

    if not hits:
        return RefusalDecision(
            True, "Không truy hồi được điều khoản nào phù hợp."
        )

    in_scope_hits = [h for h in hits if not h.provision.is_distractor]
    distractor_ratio = 1.0 - (len(in_scope_hits) / len(hits))
    top_score = hits[0].score

    if distractor_ratio >= MAX_DISTRACTOR_RATIO:
        return RefusalDecision(
            True,
            f"{distractor_ratio:.0%} kết quả truy hồi thuộc nhóm dữ liệu nhiễu "
            "(sáng chế/kiểu dáng/nhãn hiệu) — câu hỏi ngoài phạm vi quyền tác giả chương trình máy tính.",
        )

    if not in_scope_hits:
        return RefusalDecision(
            True, "Không có điều khoản thuộc phạm vi phù hợp với câu hỏi."
        )

    if top_score < MIN_SCORE_TIN_CAY:
        return RefusalDecision(
            True,
            f"Điểm tương đồng cao nhất ({top_score:.3f}) dưới ngưỡng tin cậy ({MIN_SCORE_TIN_CAY}).",
        )

    return RefusalDecision(False, "Đủ căn cứ để trả lời.")
