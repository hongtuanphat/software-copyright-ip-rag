"""generation/refusal_gate.py

Bộ lọc từ chối câu hỏi (Refusal Gate) kết hợp 3 bước:
1. Lọc từ khóa các chủ đề không liên quan (giao thông, đất đai, hình sự, thuế, ly hôn...).
2. Kiểm tra độ tin cậy của kết quả tìm kiếm (từ chối nếu không tìm thấy đoạn luật phù hợp).
3. Kiểm tra tỷ lệ tài liệu gây nhiễu (từ chối nếu đa số kết quả là về sáng chế, nhãn hiệu...).
"""
from __future__ import annotations

from dataclasses import dataclass
import config
from retrieval.retriever import RetrievalHit

# Danh sách từ khóa nhận diện các câu hỏi ngoài phạm vi Luật Sở hữu trí tuệ
OUT_OF_SCOPE_KEYWORDS = [
    # Giao thông đường bộ
    "xe máy",
    "xe ô tô",
    "vượt đèn đỏ",
    "bằng lái",
    "giấy phép lái xe",
    "nồng độ cồn",
    "vi phạm giao thông",
    "tai nạn giao thông",
    # Đất đai & Bất động sản
    "sổ đỏ",
    "sổ hồng",
    "luật đất đai",
    "sang tên sổ đỏ",
    "tranh chấp đất đai",
    "đền bù giải tỏa",
    "cấp phép xây dựng",
    # Hôn nhân & Gia đình / Dân sự
    "luật hôn nhân",
    "ly hôn",
    "chia tài sản ly hôn",
    "quyền nuôi con",
    "thừa kế",
    "di chúc",
    "cấp dưỡng",
    # Hình sự & Xử lý vi phạm
    "bộ luật hình sự",
    "tội phạm",
    "phạt tù",
    "tù giam",
    "tạm giữ",
    "tạm giam",
    "ma túy",
    "cướp giật",
    "tham ô",
    # Thuế & Lao động / Bảo hiểm
    "thuế thu nhập cá nhân",
    "quyết toán thuế",
    "hoàn thuế",
    "bảo hiểm xã hội",
    "trợ cấp thất nghiệp",
    "nghỉ thai sản",
    "hợp đồng lao động",
    "sa thải trái luật",
    "tranh chấp lao động",
]


@dataclass
class RefusalDecision:
    """Kết quả kiểm tra câu hỏi từ Refusal Gate."""
    should_refuse: bool
    reason: str


def decide(query: str, hits: list[RetrievalHit]) -> RefusalDecision:
    """Kiểm tra câu hỏi của người dùng có hợp lệ để trả lời hay cần từ chối."""
    query_low = query.lower()

    # Bước 1: Kiểm tra từ khóa câu hỏi ngoài phạm vi
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
