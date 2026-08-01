"""
generation/llm.py

Giao tiếp với mô hình ngôn ngữ lớn (LLM) để sinh câu trả lời.
Tự động fallback trích xuất nguyên văn nếu chưa cài đặt GOOGLE_API_KEY.
"""
from __future__ import annotations

import os
import config
from retrieval.retriever import RetrievalHit


def generate(query: str, prompt: str, hits: list[RetrievalHit]) -> str:
    """Sinh câu trả lời sử dụng Gemini API hoặc cơ chế fallback.

    Args:
        query: Câu hỏi của người dùng.
        prompt: Chuỗi prompt hoàn chỉnh bao gồm context.
        hits: Danh sách trích dẫn liên quan.

    Returns:
        str: Nội dung câu trả lời.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        try:
            return _call_gemini(prompt, api_key)
        except Exception as e:  # noqa: BLE001
            print(f"[LLM] Gọi Gemini API không thành công ({e}); chuyển sang fallback.")
    else:
        print("[LLM] Chưa có GOOGLE_API_KEY — sử dụng cơ chế trích xuất fallback.")

    return _extractive_fallback(query, hits)


def _call_gemini(prompt: str, api_key: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text


def _extractive_fallback(query: str, hits: list[RetrievalHit]) -> str:
    in_scope = [h for h in hits if not h.provision.is_distractor]
    if not in_scope:
        return "[Chế độ Fallback] Không tìm thấy căn cứ pháp lý phù hợp trong dữ liệu."

    top = in_scope[0].provision
    return (
        f"[Chế độ Fallback — Trích nguyên văn Điều luật]\n"
        f"Theo Điều {top.article_no} ({top.title}):\n{top.text}"
    )
