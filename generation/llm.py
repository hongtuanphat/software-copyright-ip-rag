"""generation/llm.py

Giao tiếp với mô hình Google Gemini qua SDK google-genai mới nhất.
Nếu chưa có API key hoặc mất mạng thì tự động chuyển sang trích nguyên văn điều luật điểm cao nhất.
"""
from __future__ import annotations

import os
from typing import Optional
from google import genai
from google.genai import types

import config
from retrieval.retriever import RetrievalHit
from generation.prompt_builder import SYSTEM_INSTRUCTION


def get_api_key() -> Optional[str]:
    """Lấy API key từ biến môi trường hệ thống hoặc file .env."""
    key = os.environ.get("GEMINI_API_KEY")
    return key if key else None


def generate(query: str, prompt: str, hits: list[RetrievalHit]) -> str:
    """Gọi Gemini sinh câu trả lời hoặc trích xuất điều luật nếu không có key."""
    api_key = get_api_key()
    if api_key:
        try:
            return _call_gemini(prompt, api_key)
        except Exception as e:  # noqa: BLE001
            print(f"[LLM] Không gọi được Gemini API ({e}), chuyển sang trích dẫn nguyên văn.")
    else:
        print("[LLM] Chưa có GEMINI_API_KEY — tạm thời dùng trích xuất nguyên văn.")

    return _extractive_fallback(query, hits)


def generate_no_rag(query: str) -> str:
    """Hỏi trực tiếp Gemini không kèm tài liệu luật để làm mốc đối chứng (No-RAG)."""
    api_key = get_api_key()
    if not api_key:
        return "[Baseline No-RAG] Cần có GEMINI_API_KEY để chạy thử nghiệm này."

    raw_prompt = (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"--- [TÀI LIỆU LUẬT THAM KHẢO] ---\n"
        f"(Không có tài liệu tham khảo được cung cấp. Hãy trả lời câu hỏi dựa trên kiến thức sẵn có của bạn)\n\n"
        f"--- [CÂU HỎI CỦA NGƯỜI DÙNG] ---\n"
        f"{query}\n\n"
        f"--- [CÂU TRẢ LỜI CỦA TRỢ LÝ PHÁP LÝ] ---"
    )
    return _call_gemini(raw_prompt, api_key)


def _call_gemini(prompt: str, api_key: str) -> str:
    """Gửi prompt sang Gemini và lấy văn bản kết quả."""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=config.GEMINI_MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=config.GEMINI_TEMPERATURE,
            max_output_tokens=config.GEMINI_MAX_TOKENS,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    if response and response.text:
        return response.text.strip()
    if response and response.candidates:
        parts = response.candidates[0].content.parts
        if parts and hasattr(parts[0], "text"):
            return parts[0].text.strip()
    return ""


def _extractive_fallback(query: str, hits: list[RetrievalHit]) -> str:
    """Khi không gọi được LLM, lấy nguyên văn điều luật điểm cao nhất để trả lời tạm."""
    in_scope = [h for h in hits if not h.provision.is_distractor]
    if not in_scope:
        return "[Chế độ Fallback] Không tìm thấy căn cứ pháp lý phù hợp trong dữ liệu."

    top = in_scope[0].provision
    return (
        f"[Chế độ Fallback — Trích nguyên văn Điều luật]\n"
        f"Theo Điều {top.article_no} ({top.title}):\n{top.text}"
    )
