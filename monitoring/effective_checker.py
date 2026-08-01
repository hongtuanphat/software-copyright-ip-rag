"""
monitoring/effective_checker.py

So sánh kết quả snapshot thu thập từ crawler.py với cơ sở dữ liệu hiện có.
Cập nhật trạng thái hiệu lực pháp lý (status/effective_to/replaced_by) và phát cảnh báo.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime

import config
from ingestion.chunker import Provision
from monitoring.crawler import CrawlResult, run_monthly_check


def load_chunks(path=None) -> list[Provision]:
    path = path or config.CHUNKS_PATH
    provisions = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            provisions.append(Provision(**json.loads(line)))
    return provisions


def save_chunks(provisions: list[Provision], path=None) -> None:
    path = path or config.CHUNKS_PATH
    with open(path, "w", encoding="utf-8") as f:
        for p in provisions:
            f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")


def apply_crawl_results(
    provisions: list[Provision], crawl_results: list[CrawlResult]
) -> tuple[list[Provision], list[dict]]:
    """Cập nhật thông tin hiệu lực cho danh sách các Provision dựa trên kết quả cào.

    Args:
        provisions: Danh sách các Provision hiện có.
        crawl_results: Danh sách CrawlResult từ crawler.

    Returns:
        tuple[list[Provision], list[dict]]: Danh sách Provision đã cập nhật và danh sách cảnh báo.
    """
    alerts: list[dict] = []
    now_iso = datetime.now().isoformat()

    by_law: dict[str, CrawlResult] = {r.law_code: r for r in crawl_results}

    for p in provisions:
        result = by_law.get(p.law_code)
        p.last_checked_at = now_iso
        if result is None:
            continue

        mock_path = (
            config.DATA_RAW_DIR / f"{p.law_code.replace('/', '-')}_mock_snapshot.json"
        )
        if mock_path.exists():
            mock_data = json.loads(mock_path.read_text(encoding="utf-8"))
            repl = mock_data.get("simulated_replacement")
            if repl and repl.get("old_law_code") == p.law_code:
                p.status = "bi_thay_the"
                p.replaced_by = f"{repl['new_law_code'].replace('/', '-')}_Art{p.article_no}"
                alerts.append(
                    {
                        "provision_id": p.provision_id,
                        "type": "bi_thay_the",
                        "message": (
                            f"{p.law_code} đã bị thay thế bởi "
                            f"{repl['new_law_code']} ({repl['new_issued_date']})."
                        ),
                    }
                )

        if p.effective_to:
            days_left = (date.fromisoformat(p.effective_to) - date.today()).days
            if 0 <= days_left <= config.EXPIRY_WARNING_DAYS:
                alerts.append(
                    {
                        "provision_id": p.provision_id,
                        "type": "sap_het_hieu_luc",
                        "message": f"Còn {days_left} ngày trước khi hết hiệu lực.",
                    }
                )

    return provisions, alerts


def save_alerts(alerts: list[dict], path=None) -> None:
    path = path or config.ALERTS_PATH
    with open(path, "w", encoding="utf-8") as f:
        for a in alerts:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")


def run(use_mock: bool = True) -> list[dict]:
    """Chạy quy trình kiểm tra và cập nhật hiệu lực."""
    provisions = load_chunks()
    crawl_results = run_monthly_check()
    updated, alerts = apply_crawl_results(provisions, crawl_results)
    save_chunks(updated)
    save_alerts(alerts)
    return alerts


if __name__ == "__main__":
    for alert in run():
        print(f"[CẢNH BÁO] {alert['type']} — {alert['provision_id']}: {alert['message']}")
