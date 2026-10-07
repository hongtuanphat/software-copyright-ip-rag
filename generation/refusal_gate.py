"""generation/refusal_gate.py

Bộ lọc kiểm soát và từ chối câu hỏi (Refusal Gate):
1. Lọc theo từ khóa đối với các chủ đề ngoài phạm vi chuyên môn (giao thông, đất đai, hôn nhân, hình sự, thuế, tranh chấp lao động, sáng chế, nhãn hiệu...).
   Lưu ý: Không dùng từ đơn "lao động" để tránh chặn nhầm câu hỏi hợp lệ về phần mềm tạo ra theo hợp đồng lao động (Điều 39 Luật SHTT).
2. Kiểm tra độ tin cậy của kết quả truy hồi (từ chối nếu không tìm thấy điều luật phù hợp hoặc điểm tương đồng dưới ngưỡng).
3. Kiểm tra tỷ lệ tài liệu gây nhiễu (distractor ratio) trong tập kết quả tìm kiếm.
"""
from __future__ import annotations

from dataclasses import dataclass
import config
from retrieval.retriever import RetrievalHit

# Danh sách từ khóa nhận diện câu hỏi thuộc các lĩnh vực ngoài phạm vi tư vấn bản quyền phần mềm
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
    # Hình sự & Tố tụng hình sự
    "hình sự",
    "tội phạm",
    "ma túy",
    # Thuế, Bảo hiểm & Tranh chấp lao động thuần túy
    "thuế",
    "giá trị gia tăng",
    "luật lao động",
    "bộ luật lao động",
    "tranh chấp lao động",
    "sa thải",
    "thôi việc",
    "trợ cấp thôi việc",
    "thử việc",
    "tai nạn lao động",
    "an toàn lao động",
    "đình công",
    "bảo hiểm xã hội",
    "thất nghiệp",
    "thai sản",
    # Sở hữu công nghiệp & giống cây trồng
    "logo",
    "thương hiệu",
    "sáng chế",
    "kiểu dáng công nghiệp",
    "chỉ dẫn địa lý",
    "thiết kế bố trí mạch tích hợp",
    "giống cây trồng",
    # Yêu cầu can thiệp hệ thống / Jailbreak
    "prompt injection",
    "jailbreak",
    "bỏ qua chỉ dẫn",
    "bỏ qua quy tắc",
]

# Các dấu hiệu cho thấy câu hỏi đang đề cập đến bản quyền phần mềm
IN_SCOPE_SOFTWARE_MARKERS = [
    "phần mềm",
    "chương trình máy tính",
    "mã nguồn",
    "source code",
    "bản quyền",
    "tác quyền",
    "quyền tác giả",
]


@dataclass
class RefusalDecision:
    """Kết quả kiểm tra câu hỏi từ cổng từ chối."""
    should_refuse: bool
    reason: str


def decide(
    query: str,
    hits: list[RetrievalHit],
    use_keywords: bool = True,
) -> RefusalDecision:
    """Kiểm tra câu hỏi của người dùng có đủ điều kiện trả lời hay cần từ chối."""
    query_low = query.lower()

    # Bước 1: Kiểm tra từ khóa ngoài phạm vi
    if use_keywords:
        has_software_context = any(m in query_low for m in IN_SCOPE_SOFTWARE_MARKERS)

        for kw in OUT_OF_SCOPE_KEYWORDS:
            if kw in query_low:
                # Nếu câu hỏi có ngữ cảnh phần mềm (ví dụ: làm phần mềm theo hợp đồng lao động),
                # bỏ qua từ khóa để chuyển tiếp cho bước truy hồi và LLM đánh giá chi tiết
                if has_software_context and kw in [
                    "luật lao động", "bộ luật lao động", "thử việc", "thuế"
                ]:
                    continue

                return RefusalDecision(
                    should_refuse=True,
                    reason=f"Câu hỏi thuộc chủ đề ngoài phạm vi chuyên môn ({kw}).",
                )

    # Bước 2: Kiểm tra độ tin cậy của kết quả truy hồi
    if not hits:
        return RefusalDecision(
            should_refuse=True,
            reason="Không tìm thấy điều khoản luật nào phù hợp trong dữ liệu (độ tương đồng dưới ngưỡng tin cậy).",
        )

    # Bước 3: Kiểm tra tỷ lệ tài liệu gây nhiễu trong top kết quả
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

    # Đủ căn cứ pháp lý để tiếp tục xử lý
    return RefusalDecision(should_refuse=False, reason="Đủ căn cứ để trả lời.")
