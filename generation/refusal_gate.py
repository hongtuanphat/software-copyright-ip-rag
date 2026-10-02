"""generation/refusal_gate.py

Bộ lọc từ chối câu hỏi (Refusal Gate) kết hợp 3 bước:
1. Lọc từ khóa các chủ đề không liên quan (giao thông, đất đai, hôn nhân, hình sự, thuế, lao động, sáng chế, nhãn hiệu...).
2. Kiểm tra độ tin cậy của kết quả tìm kiếm (từ chối nếu không tìm thấy đoạn luật phù hợp).
3. Kiểm tra tỷ lệ tài liệu gây nhiễu (từ chối nếu tỷ lệ distractor > MAX_DISTRACTOR_RATIO).
"""
from __future__ import annotations

from dataclasses import dataclass
import config
from retrieval.retriever import RetrievalHit

# Danh sách từ khóa nhận diện các câu hỏi ngoài phạm vi Luật Sở hữu trí tuệ
OUT_OF_SCOPE_KEYWORDS = [
    # Giao thông đường bộ
    "giao thông",
    "đường bộ",
    "xe máy",
    "ô tô",
    # Đất đai & Bất động sản
    "đất đai",
    "bất động sản",
    "sổ đỏ",
    "sổ hồng",
    # Hôn nhân & Gia đình / Dân sự
    "hôn nhân",
    "ly hôn",
    "nuôi con",
    # Hình sự & Xử lý vi phạm ngoài VBHN 67
    "hình sự",
    "tội phạm",
    "ma túy",
    # Thuế & Lao động / Bảo hiểm / Doanh nghiệp
    "thuế",
    "giá trị gia tăng",
    "lao động",
    "bảo hiểm xã hội",
    "thất nghiệp",
    "thai sản",
    # SHTT ngoài bản quyền phần mềm
    "logo",
    "thương hiệu",
    "sáng chế",
    "kiểu dáng công nghiệp",
    "chỉ dẫn địa lý",
    "thiết kế bố trí mạch tích hợp",
    "giống cây trồng",
    # Prompt injection / Jailbreak
    "prompt injection",
    "jailbreak",
    "bỏ qua chỉ dẫn",
    "bỏ qua quy tắc"
]


@dataclass
class RefusalDecision:
    """Kết quả kiểm tra câu hỏi từ Refusal Gate."""
    should_refuse: bool
    reason: str


def decide(
    query: str,
    hits: list[RetrievalHit],
    use_keywords: bool = True,
) -> RefusalDecision:
    """Kiểm tra câu hỏi của người dùng có hợp lệ để trả lời hay cần từ chối."""
    query_low = query.lower()

    # Bước 1: Kiểm tra từ khóa câu hỏi ngoài phạm vi
    if use_keywords:
        for kw in OUT_OF_SCOPE_KEYWORDS:
            if kw in query_low:
                return RefusalDecision(
                    should_refuse=True,
                    reason=f"Câu hỏi thuộc chủ đề ngoài phạm vi chuyên môn ({kw}).",
                )

    # Bước 2: Kiểm tra nếu không tìm thấy điều luật nào có độ tương đồng đạt yêu cầu
    if not hits:
        return RefusalDecision(
            should_refuse=True,
            reason="Không tìm thấy điều khoản luật nào phù hợp trong dữ liệu (độ tương đồng dưới ngưỡng tin cậy).",
        )

    # Bước 3: Kiểm tra tỷ lệ các đoạn luật gây nhiễu (distractor) trong top kết quả
    distractor_count = sum(1 for h in hits if h.provision.is_distractor)
    distractor_ratio = distractor_count / len(hits)
    if distractor_ratio > config.MAX_DISTRACTOR_RATIO:
        return RefusalDecision(
            should_refuse=True,
            reason=(
                f"Tỷ lệ dữ liệu nhiễu cao ({distractor_ratio:.1%} > "
                f"{config.MAX_DISTRACTOR_RATIO:.0%}), câu hỏi có thể không thuộc phạm vi bản quyền phần mềm."
            ),
        )


    # Đủ căn cứ để trả lời
    return RefusalDecision(should_refuse=False, reason="Đủ căn cứ để trả lời.")
