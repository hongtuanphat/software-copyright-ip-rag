"""Giao tiếp với mô hình Google Gemini qua SDK google-genai."""
from __future__ import annotations

import json
import os
import time
from enum import Enum
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

import config
from retrieval.retriever import RetrievalHit
from generation.prompt_builder import SYSTEM_INSTRUCTION


_gemini_keys: list[str] = []
_current_key_idx: int = 0


def get_api_key() -> Optional[str]:
    """Lấy API key từ biến môi trường, hỗ trợ luân phiên nhiều key (GEMINI_API_KEY_1, GEMINI_API_KEY_2,...)."""
    global _gemini_keys, _current_key_idx

    if not _gemini_keys:
        env_keys = sorted([k for k in os.environ.keys() if k.startswith("GEMINI_API_KEY")])
        for k in env_keys:
            val = os.environ.get(k, "").strip()
            if val and val not in _gemini_keys:
                _gemini_keys.append(val)

    if not _gemini_keys:
        return None

    key_to_use = _gemini_keys[_current_key_idx]
    
    _current_key_idx = (_current_key_idx + 1) % len(_gemini_keys)
    return key_to_use


def generate(query: str, prompt: str, hits: list[RetrievalHit]) -> dict:
    """Gọi Gemini với retry giới hạn cho các lỗi tạm thời."""
    first_api_key = get_api_key()
    if not first_api_key:
        raise RuntimeError("Thiếu GEMINI_API_KEY; không thể sinh câu trả lời.")

    last_error: Exception | None = None
    for attempt in range(1, config.GEMINI_MAX_ATTEMPTS + 1):
        api_key = first_api_key if attempt == 1 else get_api_key()
        if not api_key:
            raise RuntimeError("Thiếu GEMINI_API_KEY; không thể sinh câu trả lời.")
        try:
            answer_text = _call_gemini(prompt, api_key)
            if not answer_text:
                raise RuntimeError("Gemini trả về phản hồi rỗng.")
            return json.loads(answer_text)
        except json.JSONDecodeError as error:
            raise RuntimeError("Gemini trả về JSON không hợp lệ.") from error
        except Exception as error:
            last_error = error
            if attempt >= config.GEMINI_MAX_ATTEMPTS or not _is_retryable_error(error):
                break
            time.sleep(min(
                config.GEMINI_RETRY_BASE_SECONDS * (2 ** (attempt - 1)),
                30.0,
            ))

    raise RuntimeError("Gemini không khả dụng sau số lần thử cho phép.") from last_error


def _is_retryable_error(error: Exception) -> bool:
    """Chỉ retry timeout, rate limit và lỗi server có khả năng tạm thời."""
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    text = str(error).lower()
    return any(marker in text for marker in (
        "timeout", "timed out", "429", "resource_exhausted", "quota",
        "500", "502", "503", "504", "unavailable", "temporarily",
    ))


class DecisionEnum(str, Enum):
    ANSWER = "ANSWER"
    REFUSE = "REFUSE"


class RAGResponseSchema(BaseModel):
    decision: DecisionEnum = Field(description="Quyết định là ANSWER hay REFUSE")
    reason: str = Field(description="Lý do: answered, partial_context, false_premise, other_ip_object, out_of_domain, insufficient_context, prompt_injection")
    used_citations: list[int] = Field(description="Danh sách các số TÀI LIỆU được sử dụng")
    answer: str = Field(description="Nội dung câu trả lời")


def _call_gemini(prompt: str, api_key: str, timeout_ms: int = 60000) -> str:
    """Gửi prompt sang Gemini và lấy văn bản kết quả."""
    client = genai.Client(api_key=api_key, http_options={'timeout': timeout_ms})
    response = client.models.generate_content(
        model=config.GEMINI_MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=config.GEMINI_TEMPERATURE,
            max_output_tokens=config.GEMINI_MAX_TOKENS,
            response_mime_type="application/json",
            response_schema=RAGResponseSchema,
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

