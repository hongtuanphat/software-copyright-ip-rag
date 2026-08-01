"""
ingestion/chunker.py

Tách văn bản luật thành các khối dữ liệu (Provision) theo từng Điều/Khoản.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

ARTICLE_RE = re.compile(r"^Điều\s+(\d+[a-zà-ỹ]*)\.\s*(.+)$", re.IGNORECASE)
DISTRACTOR_MARKER = "DISTRACTOR"


@dataclass
class Provision:
    """Cấu trúc dữ liệu đại diện cho 1 chunk Điều hoặc Khoản luật."""

    provision_id: str
    law_code: str
    article_no: str
    clause_no: Optional[str]
    title: str
    text: str
    topic: str
    is_distractor: bool
    source_url: str
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    status: str = "hieu_luc"
    replaced_by: Optional[str] = None
    last_checked_at: Optional[str] = None
    embedding_model: Optional[str] = None
    vector_id: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


def parse_law_text(
    raw_text: str,
    law_code: str,
    source_url: str,
    topic_in_scope: str = "quyen_tac_gia_ctmt",
) -> list[Provision]:
    """Phân tích văn bản luật thô và tách thành danh sách các Provision.

    Args:
        raw_text: Nội dung văn bản luật thô.
        law_code: Mã văn bản hợp nhất (VD: '67/VBHN-VPQH').
        source_url: URL nguồn dữ liệu công khai.
        topic_in_scope: Chủ đề mặc định cho các Điều trong phạm vi.

    Returns:
        list[Provision]: Danh sách các Provision đã được chuẩn hóa.
    """
    lines = raw_text.splitlines()
    provisions: list[Provision] = []

    current_article: Optional[str] = None
    current_title: str = ""
    current_body_lines: list[str] = []
    in_distractor_zone = False

    def flush():
        if current_article is None:
            return
        body = "\n".join(current_body_lines).strip()
        if not body:
            return
        topic = _guess_topic(current_title) if in_distractor_zone else topic_in_scope
        pid = f"{law_code.replace('/', '-')}_Art{current_article}"
        provisions.append(
            Provision(
                provision_id=pid,
                law_code=law_code,
                article_no=current_article,
                clause_no=None,
                title=current_title,
                text=body,
                topic=topic,
                is_distractor=in_distractor_zone,
                source_url=source_url,
            )
        )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if DISTRACTOR_MARKER in stripped:
            in_distractor_zone = True
            continue
        m = ARTICLE_RE.match(stripped)
        if m:
            flush()
            current_article = m.group(1)
            current_title = m.group(2).strip()
            current_body_lines = []
        else:
            current_body_lines.append(stripped)
    flush()
    return provisions


def _guess_topic(title: str) -> str:
    title_low = title.lower()
    if "sáng chế" in title_low:
        return "sang_che"
    if "kiểu dáng" in title_low:
        return "kieu_dang_cong_nghiep"
    if "nhãn hiệu" in title_low:
        return "nhan_hieu"
    return "distractor_khac"


if __name__ == "__main__":
    import config

    raw_path = config.DATA_RAW_DIR / "67-VBHN-VPQH.txt"
    text = raw_path.read_text(encoding="utf-8")
    result = parse_law_text(
        text,
        law_code=config.LAW_CODE,
        source_url="https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-67-vbhn-vpqh-469197.htm",
    )
    print(f"Đã tách được {len(result)} provisions:")
    for p in result:
        flag = "[DISTRACTOR]" if p.is_distractor else ""
        print(f"  - Điều {p.article_no}: {p.title} {flag}")
