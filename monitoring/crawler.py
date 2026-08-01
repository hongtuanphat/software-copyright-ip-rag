"""
monitoring/crawler.py

Module cào và cập nhật dữ liệu pháp luật định kỳ từ các cổng thông tin chính thức, 
phục vụ theo dõi và quản lý hiệu lực văn bản.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Literal

import config


@dataclass
class CrawlResult:
    law_code: str
    status: Literal["ok", "blocked_by_captcha", "blocked_by_robots", "error", "mock"]
    snapshot_date: str
    raw_text: str | None
    detail: str = ""


def check_robots_allowed(base_url: str, path: str, user_agent: str) -> bool:
    """Kiểm tra quyền cào dữ liệu theo tệp robots.txt của trang đích.

    Args:
        base_url: URL gốc của trang thông tin pháp luật.
        path: Đường dẫn tới tài liệu cần lấy dữ liệu.
        user_agent: Tên định danh của crawler.

    Returns:
        bool: True nếu được phép cào, False nếu bị cấm hoặc lỗi.
    """
    import urllib.robotparser

    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{base_url}/robots.txt")
    try:
        rp.read()
    except Exception:
        return False
    return rp.can_fetch(user_agent, base_url + path)


def fetch_snapshot(law_code: str, use_mock: bool = True) -> CrawlResult:
    """Lấy thông tin snapshot mới nhất của văn bản pháp luật theo mã văn bản.

    Args:
        law_code: Mã văn bản hợp nhất (VD: '67/VBHN-VPQH').
        use_mock: Nếu True, đọc dữ liệu giả lập từ tệp mock trong data/raw.

    Returns:
        CrawlResult: Kết quả cào dữ liệu.
    """
    if use_mock:
        mock_path = config.DATA_RAW_DIR / f"{law_code.replace('/', '-')}_mock_snapshot.json"
        if not mock_path.exists():
            return CrawlResult(
                law_code=law_code,
                status="error",
                snapshot_date=str(date.today()),
                raw_text=None,
                detail=f"Không tìm thấy mock snapshot tại {mock_path}",
            )
        data = json.loads(mock_path.read_text(encoding="utf-8"))
        return CrawlResult(
            law_code=law_code,
            status="mock",
            snapshot_date=data.get("snapshot_date", str(date.today())),
            raw_text=data.get("raw_text"),
            detail="Dữ liệu mock kiểm thử pipeline.",
        )

    raise NotImplementedError(
        "Chức năng cào trực tuyến từ nguồn chính thức sẽ được kích hoạt ở Tuần 5."
    )


def run_monthly_check(law_codes: list[str] | None = None) -> list[CrawlResult]:
    """Chạy kiểm tra định kỳ hàng tháng cho danh sách các văn bản cần theo dõi."""
    law_codes = law_codes or config.MONITORED_LAWS
    return [fetch_snapshot(lc, use_mock=True) for lc in law_codes]


if __name__ == "__main__":
    for result in run_monthly_check():
        print(result)
