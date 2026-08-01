"""
ingestion/metadata.py

Xử lý và gán dữ liệu thuộc tính (metadata) cho các khối văn bản (Provision).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ingestion.chunker import Provision


def load_law_meta(raw_txt_path: Path) -> dict:
    """Đọc tệp metadata .meta.json tương ứng với văn bản thô."""
    meta_path = raw_txt_path.with_suffix(".meta.json")
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def attach_effective_metadata(
    provisions: list[Provision], law_meta: dict
) -> list[Provision]:
    """Gán thông tin hiệu lực pháp lý ban đầu cho danh sách các Provision.

    Args:
        provisions: Danh sách Provision cần xử lý.
        law_meta: Dict chứa thông tin metadata của văn bản luật.

    Returns:
        list[Provision]: Danh sách Provision đã được đính kèm metadata.
    """
    now_iso = datetime.now(timezone(_vn_offset())).isoformat()
    effective_from = law_meta.get("issued_date")
    for p in provisions:
        p.effective_from = effective_from
        p.last_checked_at = now_iso
    return provisions


def _vn_offset():
    from datetime import timedelta

    return timedelta(hours=7)
