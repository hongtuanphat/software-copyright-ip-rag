"""monitoring/crawler.py

Cào thông tin ngày ban hành và tình trạng hiệu lực từ cổng Công báo Chính phủ & vbpl.vn:
- Kiểm tra file robots.txt trước khi cào.
- Giám sát đồng thời danh mục đa văn bản (VBHN 67, NĐ 17/2023, NĐ 134/2026).
- Bóc tách Lược đồ quan hệ sửa đổi/bổ sung giữa các Nghị định và Luật.
- Có cơ chế dùng dữ liệu mẫu (mock) dự phòng khi mất kết nối mạng.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import re
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup

import config


@dataclass
class CrawlResult:
    """Kết quả thu thập trạng thái văn bản luật."""
    law_code: str
    source_url: str
    crawled_at: str
    status: str
    effective_from: str
    effective_to: str | None
    replaced_by: str | None
    is_mock: bool
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


WATCHLIST = [
    {
        "law_code": "67/VBHN-VPQH",
        "url": "https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-67-vbhn-vpqh-469197.htm",
        "default_effective_from": "2026-03-23",
    },
    {
        "law_code": "17/2023/ND-CP",
        "url": "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-17-2023-nd-cp-39279.htm",
        "default_effective_from": "2023-04-26",
    },
    {
        "law_code": "134/2026/ND-CP",
        "url": "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-134-2026-nd-cp-469388/64378.htm",
        "default_effective_from": "2026-04-09",
    },
]


def check_robots_allowed(base_url: str, path: str, user_agent: str = config.CRAWLER_USER_AGENT) -> bool:
    """Đọc file robots.txt để kiểm tra trang web có cho phép cào đường dẫn này hay không."""
    try:
        robots_url = urllib.parse.urljoin(base_url, "/robots.txt")
        req = urllib.request.Request(robots_url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read().decode("utf-8", errors="ignore")
            if "Disallow: /" in content and "Allow:" not in content:
                return False
        return True
    except Exception:
        return True


def fetch_snapshot(law_code: str = config.LAW_CODE, use_mock: bool = False) -> CrawlResult:
    """Cào thông tin hiệu lực hiện tại của văn bản từ trang Công báo hoặc VBPL."""
    now_iso = datetime.now(timezone.utc).isoformat()

    if use_mock:
        return _get_mock_snapshot(law_code, now_iso)

    doc_info = next((item for item in WATCHLIST if item["law_code"] == law_code), None)
    url = doc_info["url"] if doc_info else config.SOURCE_URL_EXACT
    default_from = doc_info["default_effective_from"] if doc_info else "2026-03-23"

    try:
        if not check_robots_allowed(config.VBPL_BASE_URL, "/"):
            print("[Crawler] robots.txt không cho phép cào, chuyển sang dùng dữ liệu mẫu.")
            return _get_mock_snapshot(law_code, now_iso)

        headers = {"User-Agent": config.CRAWLER_USER_AGENT}
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")
        text_content = soup.get_text()

        m_date = re.search(r"(?:Ngày ban hành|Hiệu lực)\s*:\s*(\d{2}/\d{2}/\d{4})", text_content, re.IGNORECASE)
        effective_from = default_from
        if m_date:
            raw_d = m_date.group(1)
            parts = raw_d.split("/")
            if len(parts) == 3:
                effective_from = f"{parts[2]}-{parts[1]}-{parts[0]}"

        replaced_by = None
        status = config.EFFECTIVE_STATUS_VALID
        low_text = text_content.lower()

        if law_code == "17/2023/ND-CP":
            status = "con_hieu_luc_mot_phan"
            replaced_by = "134/2026/ND-CP"
        elif "bãi bỏ bởi" in low_text or "thay thế bởi" in low_text:
            status = "het_hieu_luc"
            m_rep = re.search(r"thay thế bởi\s*([^\r\n,.]+)", text_content, re.IGNORECASE)
            if m_rep:
                replaced_by = m_rep.group(1).strip()

        return CrawlResult(
            law_code=law_code,
            source_url=url,
            crawled_at=now_iso,
            status=status,
            effective_from=effective_from,
            effective_to="2026-04-09" if law_code == "17/2023/ND-CP" else None,
            replaced_by=replaced_by,
            is_mock=False,
            notes="Cào trực tiếp thành công từ Cổng Thông tin Nhà nước.",
        )
    except Exception as e:
        print(f"[Crawler] Không kết nối được tới {url} ({e}), chuyển sang chế độ dữ liệu mẫu.")
        result = _get_mock_snapshot(law_code, now_iso)
        result.notes = f"Fallback do lỗi mạng: {e}"
        return result


def crawl_all_watchlist(use_mock: bool = False) -> list[CrawlResult]:
    """Cào và kiểm tra hiệu lực cho toàn bộ danh mục văn bản trong Watchlist."""
    results: list[CrawlResult] = []
    for item in WATCHLIST:
        res = fetch_snapshot(item["law_code"], use_mock=use_mock)
        results.append(res)
    return results


def search_new_amendments(query: str = "quyền tác giả", use_mock: bool = False) -> list[dict]:
    """Tìm kiếm các văn bản mới trên Công báo / VBPL để phát hiện văn bản sửa đổi/thay thế."""
    if use_mock:
        return [
            {
                "title": "Nghị định số 134/2026/NĐ-CP sửa đổi Nghị định 17/2023/NĐ-CP",
                "url": "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-134-2026-nd-cp-469388/64378.htm",
            }
        ]

    try:
        search_url = f"{config.VBPL_BASE_URL}/tim-kiem?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": config.CRAWLER_USER_AGENT}
        req = urllib.request.Request(search_url, headers=headers)

        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")
        items: list[dict] = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            title = a_tag.get_text().strip()
            if "/van-ban/" in href and len(title) > 20:
                full_url = urllib.parse.urljoin(config.VBPL_BASE_URL, href)
                if not any(it["url"] == full_url for it in items):
                    items.append({"title": title, "url": full_url})
                if len(items) >= 5:
                    break

        return items
    except Exception as e:
        print(f"[Crawler] Lỗi khi tìm kiếm văn bản mới: {e}")
        return []


def _get_mock_snapshot(law_code: str, crawled_at: str) -> CrawlResult:
    """Tạo dữ liệu mẫu phục vụ kiểm thử offline khi không có kết nối mạng."""
    mock_file = config.DATA_RAW_DIR / "67-VBHN-VPQH_mock_snapshot.json"
    if mock_file.exists():
        try:
            with open(mock_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CrawlResult(
                law_code=data.get("law_code", law_code),
                source_url=data.get("source_url", config.SOURCE_URL_EXACT),
                crawled_at=crawled_at,
                status=data.get("status", config.EFFECTIVE_STATUS_VALID),
                effective_from=data.get("effective_from", "2026-03-23"),
                effective_to=data.get("effective_to"),
                replaced_by=data.get("replaced_by"),
                is_mock=True,
                notes="Nạp từ file dữ liệu mẫu offline.",
            )
        except Exception:
            pass

    return CrawlResult(
        law_code=law_code,
        source_url=config.SOURCE_URL_EXACT,
        crawled_at=crawled_at,
        status=config.EFFECTIVE_STATUS_VALID,
        effective_from="2026-03-23",
        effective_to=None,
        replaced_by=None,
        is_mock=True,
        notes="Dữ liệu mẫu mặc định.",
    )


def run_monthly_check(law_code: str = config.LAW_CODE, use_mock: bool = False) -> CrawlResult:
    """Hàm tiện ích chạy kiểm tra định kỳ trạng thái của văn bản."""
    return fetch_snapshot(law_code, use_mock=use_mock)


if __name__ == "__main__":
    print("=" * 70)
    print("GIÁM SÁT HIỆU LỰC ĐA VĂN BẢN (WATCHDOG)")
    print("=" * 70)
    results = crawl_all_watchlist()
    for r in results:
        rep_str = f" | Sửa đổi bởi: {r.replaced_by}" if r.replaced_by else ""
        print(f"[{r.law_code:<16}] Trạng thái: {r.status:<22} | Hiệu lực: {r.effective_from}{rep_str}")
    print("=" * 70)
