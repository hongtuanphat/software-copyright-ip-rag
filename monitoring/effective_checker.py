"""monitoring/effective_checker.py

Kiểm tra và cập nhật trạng thái hiệu lực văn bản:
- So sánh thông tin cào được với danh sách các đoạn luật trong chunks.jsonl.
- Phát cảnh báo nếu văn bản sắp hết hiệu lực (trước 45 ngày) hoặc bị thay thế.
- Ghi nhật ký cảnh báo vào alerts.jsonl và có cache trong bộ nhớ để đọc nhanh.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Sequence

import config
from ingestion.chunker import Provision
from monitoring.crawler import CrawlResult, run_monthly_check


def load_chunks(path: Path | None = None) -> list[Provision]:
    """Đọc danh sách các đoạn luật từ file chunks.jsonl."""
    target = path or config.CHUNKS_PATH
    if not target.exists():
        return []
    provisions: list[Provision] = []
    with open(target, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                provisions.append(Provision(**json.loads(line)))
    return provisions


def save_chunks(provisions: list[Provision], path: Path | None = None) -> None:
    """Lưu lại danh sách các đoạn luật sau khi đã cập nhật trạng thái."""
    target = path or config.CHUNKS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        for p in provisions:
            data = p.to_dict()
            f.write(json.dumps(data, ensure_ascii=False) + "\n")


def check_expiring_soon(effective_to: str | None, warning_days: int = config.EXPIRY_WARNING_DAYS) -> bool:
    """Kiểm tra xem văn bản có sắp hết hiệu lực trong số ngày quy định hay không."""
    if not effective_to:
        return False
    try:
        exp_date = datetime.fromisoformat(effective_to.replace("Z", "+00:00"))
        if exp_date.tzinfo is None:
            exp_date = exp_date.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_left = (exp_date - now).days
        return 0 <= days_left <= warning_days
    except Exception:
        return False


def apply_crawl_results(
    crawl_results: CrawlResult | Sequence[CrawlResult],
    provisions: list[Provision],
) -> tuple[list[Provision], list[dict]]:
    """Cập nhật trạng thái hiệu lực vào các đoạn luật và tạo danh sách cảnh báo nếu có."""
    updated: list[Provision] = []
    alerts: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    snapshots = [crawl_results] if isinstance(crawl_results, CrawlResult) else list(crawl_results)

    for snapshot in snapshots:
        is_expiring = check_expiring_soon(snapshot.effective_to)
        is_replaced = snapshot.status == "het_hieu_luc" or bool(snapshot.replaced_by)

        if is_expiring:
            alerts.append({
                "law_code": snapshot.law_code,
                "alert_type": "EXPIRING_SOON",
                "effective_to": snapshot.effective_to,
                "created_at": now_iso,
                "message": f"Văn bản {snapshot.law_code} sắp hết hiệu lực vào ngày {snapshot.effective_to}.",
            })

        if is_replaced:
            alerts.append({
                "law_code": snapshot.law_code,
                "alert_type": "REPLACED",
                "replaced_by": snapshot.replaced_by,
                "created_at": now_iso,
                "message": f"Văn bản {snapshot.law_code} đã hết hiệu lực, được thay thế bởi {snapshot.replaced_by or 'văn bản mới'}.",
            })

        for p in provisions:
            if p.law_code == snapshot.law_code:
                p.status = snapshot.status
                p.effective_to = snapshot.effective_to
                p.replaced_by = snapshot.replaced_by
            if p not in updated:
                updated.append(p)

    return updated if updated else list(provisions), alerts


def save_alerts(alerts: list[dict], path: Path | None = None, alerts_path: Path | None = None) -> None:
    """Ghi danh sách cảnh báo vào file alerts.jsonl."""
    if not alerts:
        return
    target = path or alerts_path or config.ALERTS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        for a in alerts:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")


# Cache trong bộ nhớ để không phải đọc lại file nhiều lần
_ALERT_CACHE: list[dict] = []
_ALERT_CACHE_MTIME: float = 0.0


def get_active_alerts(path: Path | None = None, alerts_path: Path | None = None) -> list[dict]:
    """Lấy danh sách các cảnh báo hiệu lực đang hoạt động (có dùng cache bộ nhớ)."""
    global _ALERT_CACHE, _ALERT_CACHE_MTIME
    target = path or alerts_path or config.ALERTS_PATH
    if not target.exists():
        return []

    try:
        current_mtime = target.stat().st_mtime
        if current_mtime == _ALERT_CACHE_MTIME and _ALERT_CACHE:
            return _ALERT_CACHE

        alerts: list[dict] = []
        with open(target, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    alerts.append(json.loads(line))

        _ALERT_CACHE = alerts
        _ALERT_CACHE_MTIME = current_mtime
        return _ALERT_CACHE
    except Exception:
        return _ALERT_CACHE


def run(use_mock: bool = False) -> None:
    """Hàm chính thực hiện quy trình kiểm tra và cập nhật hiệu lực."""
    print("--- Đang kiểm tra trạng thái hiệu lực văn bản từ Công báo ---")
    snapshot = run_monthly_check(use_mock=use_mock)
    print(f"Kết quả cào: {snapshot.law_code} | Trạng thái: {snapshot.status} | Ngày ban hành: {snapshot.effective_from}")

    provisions = load_chunks()
    if not provisions:
        print("Chưa có dữ liệu chunks.jsonl để cập nhật.")
        return

    updated_provs, alerts = apply_crawl_results(snapshot, provisions)
    save_chunks(updated_provs)
    save_alerts(alerts)

    if alerts:
        print(f"Phát hiện {len(alerts)} cảnh báo mới:")
        for a in alerts:
            print(f"  - [{a['alert_type']}] {a['message']}")
    else:
        print("Văn bản vẫn đang có hiệu lực bình thường, không có cảnh báo mới.")


if __name__ == "__main__":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    run()
