"""
ingestion/chunker.py

Tách văn bản luật thành các khối dữ liệu (Provision) theo từng Điều/Khoản.
Hỗ trợ tách sâu xuống cấp Khoản (Clause Chunking) ở Tuần 2.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Optional

ARTICLE_RE = re.compile(r"^Điều\s+(\d+[a-zà-ỹ]*)\.\s*(.+)$", re.IGNORECASE)
CLAUSE_RE = re.compile(r"^(\d+)\.\s+(.*)$")
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
    """Phân tích văn bản luật thô và tách thành danh sách các Provision cấp Khoản/Điều.

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
    current_article_lines: list[str] = []
    in_distractor_zone = False

    def process_article(art_no: str, art_title: str, body_lines: list[str], is_dist: bool):
        if not art_no or not body_lines:
            return
        
        topic = _guess_topic(art_title) if is_dist else topic_in_scope
        sanitized_code = law_code.replace("/", "-")
        
        # Kiểm tra xem Điều có phân tách các Khoản bằng '1.', '2.', '3.' hay không
        clause_blocks: list[tuple[Optional[str], list[str]]] = []
        curr_clause_no: Optional[str] = None
        curr_clause_lines: list[str] = []

        for b_line in body_lines:
            c_match = CLAUSE_RE.match(b_line)
            if c_match:
                if curr_clause_lines or curr_clause_no is not None:
                    clause_blocks.append((curr_clause_no, curr_clause_lines))
                curr_clause_no = c_match.group(1)
                curr_clause_lines = [b_line]
            else:
                curr_clause_lines.append(b_line)
        
        if curr_clause_lines or curr_clause_no is not None:
            clause_blocks.append((curr_clause_no, curr_clause_lines))

        # Tạo Provision cho từng khối Khoản (hoặc cả Điều nếu không chia Khoản)
        if len(clause_blocks) == 1 and clause_blocks[0][0] is None:
            c_no, c_lines = clause_blocks[0]
            body_text = "\n".join(c_lines).strip()
            if body_text:
                pid = f"{sanitized_code}_Art{art_no}"
                provisions.append(
                    Provision(
                        provision_id=pid,
                        law_code=law_code,
                        article_no=art_no,
                        clause_no=None,
                        title=art_title,
                        text=body_text,
                        topic=topic,
                        is_distractor=is_dist,
                        source_url=source_url,
                    )
                )
        else:
            for c_no, c_lines in clause_blocks:
                body_text = "\n".join(c_lines).strip()
                if not body_text:
                    continue
                clause_suffix = f"_Kh{c_no}" if c_no else ""
                pid = f"{sanitized_code}_Art{art_no}{clause_suffix}"
                provisions.append(
                    Provision(
                        provision_id=pid,
                        law_code=law_code,
                        article_no=art_no,
                        clause_no=c_no,
                        title=art_title,
                        text=body_text,
                        topic=topic,
                        is_distractor=is_dist,
                        source_url=source_url,
                    )
                )

    def flush():
        nonlocal current_article, current_title, current_article_lines
        if current_article is not None and current_article_lines:
            process_article(current_article, current_title, current_article_lines, in_distractor_zone)
        current_article = None
        current_title = ""
        current_article_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if DISTRACTOR_MARKER in stripped:
            flush()
            in_distractor_zone = True
            continue
        m = ARTICLE_RE.match(stripped)
        if m:
            flush()
            current_article = m.group(1)
            current_title = m.group(2).strip()
            current_article_lines = []
        else:
            current_article_lines.append(stripped)
    flush()
    return provisions


def _guess_topic(title: str) -> str:
    """Phân loại chủ đề distractor dựa trên tiêu đề điều luật.

    Các nhóm distractor phấn đấu xuất hiện trong văn bản SHTT nhưng nàm ngoài phạm vi trả lời:
    - Quyền liên quan (người biểu diễn, bản ghi âm, chương trình phát sóng)
    - Sáng chế (thuật toán, giải pháp kỹ thuật)
    - Kiểu dáng công nghiệp (giao diện UI/UX bên ngoài)
    - Nhãn hiệu / Tên thương mại (logo, thương hiệu app)
    - Bí mật kinh doanh
    """
    title_low = title.lower()
    if "sáng chế" in title_low:
        return "sang_che"
    if "kiểu dáng" in title_low:
        return "kieu_dang_cong_nghiep"
    if "nhãn hiệu" in title_low or "tên thương mại" in title_low:
        return "nhan_hieu"
    if "biểu diễn" in title_low or "bản ghi" in title_low or "quyền liên quan" in title_low:
        return "quyen_lien_quan"
    if "bí mật kinh doanh" in title_low:
        return "bi_mat_kinh_doanh"
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
    print(f"Đã tách được {len(result)} provisions (cấp Khoản/Điều):")
    for p in result:
        flag = "[DISTRACTOR]" if p.is_distractor else ""
        c_str = f" Khoản {p.clause_no}" if p.clause_no else ""
        print(f"  - Điều {p.article_no}{c_str}: {p.title} ({p.provision_id}) {flag}")
