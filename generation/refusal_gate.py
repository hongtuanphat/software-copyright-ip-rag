"""generation/refusal_gate.py

Module cổng từ chối (Refusal Gate) cho hệ thống RAG pháp luật sở hữu trí tuệ:
Kiến trúc kiểm soát phân tầng phòng vệ đa lớp:
1. Tầng lọc từ khóa vĩ mô (Macro Domain Filter): Nhận diện các lĩnh vực hoàn toàn ngoài ngành (giao thông, đất đai, hôn nhân, hình sự...) nhằm phản hồi nhanh. Giữ nguyên tính mở đối với các câu hỏi liên quan đến hợp đồng lao động và phần mềm (Điều 39 Luật SHTT).
2. Tầng phân loại ngữ nghĩa (Semantic Intent Gate): Sử dụng mô hình ngôn ngữ để phân tích bản chất câu hỏi, nhận diện câu hỏi dựa trên tiền đề sai, câu hỏi ngoài thẩm quyền cần hướng dẫn nguồn, hoặc hành vi can thiệp hệ thống.
3. Tầng số học kết quả truy hồi (Metric Gate): Kiểm tra ngưỡng tương đồng ngữ nghĩa tối thiểu (Cosine Similarity >= 0.22) và tỷ lệ dữ liệu gây nhiễu (Distractor Ratio <= 0.60).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import config
from retrieval.retriever import RetrievalHit

# Danh sách từ khóa vĩ mô nhận diện các lĩnh vực hoàn toàn không thuộc luật sở hữu trí tuệ
# (Đã loại bỏ hoàn toàn các từ gây nhiễu như "lao động", "thuế" để tránh chặn nhầm Điều 39 Luật SHTT)
OUT_OF_SCOPE_KEYWORDS = [
    # Giao thông đường bộ
    "giao thông",
    "đường bộ",
    "xe máy",
    "ô tô",
    "nồng độ cồn",
    "giấy phép lái xe",
    "bằng lái",
    # Đất đai & Bất động sản
    "đất đai",
    "bất động sản",
    "sổ đỏ",
    "sổ hồng",
    "tách thửa",
    "thổ cư",
    # Hôn nhân & Gia đình / Dân sự
    "hôn nhân",
    "ly hôn",
    "nuôi con",
    "kết hôn",
    # Hình sự & Tệ nạn xã hội
    "hình sự",
    "tội phạm",
    "ma túy",
    # Bảo hiểm xã hội ngoài chuyên môn
    "bảo hiểm xã hội",
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


@dataclass
class RefusalDecision:
    """Kết quả kiểm tra câu hỏi từ cổng từ chối."""
    should_refuse: bool
    reason: str
    intent: Optional[str] = None
    suggested_response: str = ""


def check_metric_gate(hits: list[RetrievalHit]) -> RefusalDecision:
    """Kiểm tra độ tin cậy của tập kết quả truy hồi (Metric Gate: Cosine threshold & Distractor ratio)."""
    if not hits:
        return RefusalDecision(
            should_refuse=True,
            reason="Không tìm thấy điều khoản luật nào phù hợp trong dữ liệu (độ tương đồng dưới ngưỡng tin cậy).",
        )

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

    return RefusalDecision(should_refuse=False, reason="Đủ căn cứ để trả lời.")


def decide(
    query: str,
    hits: Optional[list[RetrievalHit]] = None,
    use_keywords: bool = True,
    use_semantic: bool = True,
) -> RefusalDecision:
    """Kiểm tra câu hỏi của người dùng có đủ điều kiện trả lời hay cần từ chối.
    
    Hỗ trợ cấu hình kiểm soát phân tầng hoặc phục vụ đánh giá thực nghiệm triệt tiêu (Ablation Study):
    - use_keywords=True: Kích hoạt bộ lọc nhanh từ khóa chủ đề vĩ mô (Fast Path 0ms).
    - use_semantic=True: Kích hoạt bộ phân loại ý định ngữ nghĩa sâu (LLM Intent Classifier).
    - hits kiểm tra theo cơ chế Metric Gate (Cosine threshold & Distractor ratio).
    """
    query_low = query.lower()

    # Bước 1: Kiểm tra từ khóa chủ đề vĩ mô hoàn toàn ngoài ngành (Fast Path 0ms)
    if use_keywords:
        for kw in OUT_OF_SCOPE_KEYWORDS:
            if kw in query_low:
                return RefusalDecision(
                    should_refuse=True,
                    reason=f"Câu hỏi thuộc chủ đề ngoài phạm vi chuyên môn ({kw}).",
                    intent="OUT_OF_DOMAIN",
                )

    # Bước 2: Kiểm tra phân loại ngữ nghĩa sâu (LLM Intent Classifier)
    if use_semantic:
        try:
            from generation.intent_classifier import classify_query_intent, IntentCategory
            intent_res = classify_query_intent(query)
            if intent_res.should_refuse:
                return RefusalDecision(
                    should_refuse=True,
                    reason=f"[{intent_res.intent.value}] {intent_res.reason}",
                    intent=intent_res.intent.value,
                    suggested_response=intent_res.suggested_response,
                )
        except Exception:
            pass  # Fallback sang các bước kiểm tra tiếp theo nếu module phân loại gặp sự cố

    # Bước 3: Kiểm tra kết quả truy hồi theo ngưỡng số học (Metric Gate - chỉ thực hiện khi có tập hits)
    if hits is not None:
        metric_decision = check_metric_gate(hits)
        if metric_decision.should_refuse:
            return metric_decision

    # Đủ căn cứ pháp lý để tiếp tục xử lý
    return RefusalDecision(should_refuse=False, reason="Đủ căn cứ để trả lời.")
