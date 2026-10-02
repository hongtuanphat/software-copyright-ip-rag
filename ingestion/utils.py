"""Shared text preparation helpers for legal provision indexing."""
from __future__ import annotations

import re

from pyvi import ViTokenizer

from ingestion.chunker import Provision


def tokenize_vietnamese(text: str) -> str:
    """Segment Vietnamese syllables into model-friendly compound tokens."""
    return ViTokenizer.tokenize(text)


def build_index_text(provision: Provision) -> str:
    """Build the canonical text representation used by every index."""
    clause = f" Khoản {provision.clause_no}." if provision.clause_no else ""
    return (
        f"[{provision.law_code}] Điều {provision.article_no}. "
        f"{provision.title}{clause} {provision.text}"
    ).strip()


def tokenize_for_bm25(text: str) -> list[str]:
    """Return Vietnamese word and adjacent phrase tokens for BM25."""
    segmented = tokenize_vietnamese(text).lower()
    words = re.findall(r"[\w]+", segmented, flags=re.UNICODE)
    if not words:
        return []
    bigrams = [f"{words[i]}_{words[i + 1]}" for i in range(len(words) - 1)]
    return words + bigrams
