"""generation/citation_resolver.py

Chịu trách nhiệm chuẩn hóa, làm sạch và ánh xạ các trích dẫn (citations) từ đầu ra JSON của LLM.
Thực hiện các công việc:
- Validate (đảm bảo index nằm trong giới hạn).
- Deduplicate (loại bỏ index trùng).
- Sanitize Text (giữ marker hợp lệ và xóa marker ngoài context).
- Resolve Documents (ánh xạ ngược index thành các object Provision thực tế).
"""
import re
from typing import Any

def extract_citation_indices(answer_text: str) -> list[int]:
    """Extract unique citation markers in their order of appearance."""
    seen: list[int] = []
    for value in re.findall(r"\[(\d+)\]", answer_text or ""):
        index = int(value)
        if index not in seen:
            seen.append(index)
    return seen

def resolve_citations(
    answer_text: str, 
    raw_used_citations: list, 
    context_documents: list[Any]
) -> tuple[str, list[Any], list[int]]:
    """
    Xử lý raw_used_citations từ LLM và làm sạch answer_text.
    
    Args:
        answer_text: Văn bản câu trả lời có chứa các marker trích dẫn dạng [i].
        raw_used_citations: Mảng index JSON của LLM, giữ lại vì tương thích API.
        context_documents: Mảng tài liệu visible, được đánh số từ 1 trong prompt.
        
    Returns:
        tuple gồm: (answer_text đã loại marker sai, cited_documents, index parse từ text)
    """
    # The answer is the observable citation contract. The model's JSON list is
    # retained for API compatibility but cannot add citations absent from text.
    parsed_citations = extract_citation_indices(answer_text)
    used_citations = [
        index for index in parsed_citations
        if 1 <= index <= len(context_documents)
    ]
    
    # Remove markers that do not point to a visible prompt document.
    def _replacer(match):
        val = int(match.group(1))
        if val in used_citations:
            return f"[{val}]"
        return ""
        
    cleaned_answer = re.sub(r"\[(\d+)\]", _replacer, answer_text) if answer_text else ""
    
    cited_documents = []
    for index in used_citations:
        document = dict(context_documents[index - 1])
        document["citation_index"] = index
        cited_documents.append(document)
    
    return cleaned_answer, cited_documents, used_citations
