"""Chuyển đổi tập câu hỏi đối chứng Excel sang định dạng JSON (questions.json).

[
  {
    "id": "...",
    "group": "...",
    "question": "...",
    "gold_ids": ["..."],
    "answer": "...",
    "source_url": "...",
    "law_code": "...",
    "article_no": "...",
    "clause_no": "...",
    "status": "...",
    "citation": "...",
    "expected_behavior": "...",
    "notes": "..."
  }
]

"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.convert_dev_set import (
    build_gold_ids,
    load_excel,
    normalize_group,
    normalize_text,
    parse_article_numbers,
    parse_clause_numbers,
    warn,
    WARNING_MESSAGES,
)

DEFAULT_INPUT = Path("data/evaluation/gold_questions.xlsx")
DEFAULT_OUTPUT = Path("data/evaluation/questions.json")


def normalize_number_list(raw_value: Any) -> str:
    import re as _re

    text = normalize_text(raw_value)
    if not text:
        return ""
    text = _re.sub(r"\s+và\s+", ", ", text, flags=_re.IGNORECASE)
    text = _re.sub(r"(\d)\.(?=\d)", r"\1, ", text)
    text = _re.sub(r"\s*,\s*", ", ", text)
    return text.strip()


def map_expected_behavior(raw_value: Any) -> str:
    s = normalize_text(raw_value).lower()
    if "từ chối" in s or "tu_choi" in s:
        return "tu_choi"
    if "trả lời" in s or "tra_loi" in s:
        return "tra_loi"
    return normalize_text(raw_value)


def map_status(raw_status: Any) -> str:
    s = normalize_text(raw_status).lower()
    if "hết" in s or "het_hieu_luc" in s:
        return "het_hieu_luc"
    if "còn" in s or "có hiệu lực" in s or "hieu_luc" in s:
        return "hieu_luc"
    return "hieu_luc"


def convert_questions(df: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for row_index, row in df.iterrows():
        row_number = row_index + 2  # Excel line tính từ 2 (header row = 1)

        raw_id = normalize_text(row.get("ID"))
        if not raw_id:
            warn(f"Bỏ qua dòng {row_number}: thiếu ID.")
            continue

        row_id = str(raw_id)
        if row_id in seen_ids:
            warn(f"ID '{row_id}' bị trùng lặp ở dòng {row_number}. Bỏ qua dòng này.")
            continue
        
        seen_ids.add(row_id)

        question = normalize_text(row.get("Cau_hoi"))
        if not question:
            warn(f"ID '{row_id}' không có nội dung Cau_hoi hợp lệ; sẽ bỏ record này.")
            continue

        record = {
            "id": row_id,
            "group": normalize_group(row.get("Nhom")),
            "question": question,
            "gold_ids": [],
            "answer": normalize_text(row.get("Cau_tra_loi_gold")),
            "source_url": normalize_text(row.get("Van_ban_nguon")),
            "law_code": normalize_text(row.get("Ma_van_ban_ky_vong")),
            "article_no": normalize_number_list(row.get("Dieu_ky_vong")),
            "clause_no": normalize_number_list(row.get("Khoan_ky_vong")),
            "status": map_status(row.get("Tinh_trang_hieu_luc_ky_vong")),
            "citation": normalize_text(row.get("Trich_dan")),
            "expected_behavior": map_expected_behavior(row.get("Hanh_vi_ky_vong")),
            "notes": normalize_text(row.get("Ghi_chu_dat_biet")),
        }

        # Xử lý gold_ids
        law_code = record["law_code"]
        if law_code:
            article_values = parse_article_numbers(row.get("Dieu_ky_vong"))
            clause_values = parse_clause_numbers(row.get("Khoan_ky_vong"))

            if article_values:
                gold_ids_set = set(build_gold_ids(law_code, article_values, clause_values))
                record["gold_ids"] = sorted(list(gold_ids_set))
            else:
                warn(
                    f"ID '{row_id}' có Mã văn bản '{law_code}' nhưng không có "
                    "Dieu_ky_vong hợp lệ; không tạo gold_ids."
                )
        else:
            warn(
                f"ID '{row_id}' thiếu Ma_van_ban_ky_vong; "
                f"bỏ qua tạo gold_ids ở dòng {row_number}."
            )

        records.append(record)

    return records


def save_json(records: list[dict[str, Any]], output_path: Path) -> None:
    """Lưu danh sách JSON theo UTF-8 và indent 2."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Chuyển đổi gold_questions.xlsx thành questions.json "
            "phục vụ end-to-end evaluation."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Đường dẫn tới file Excel đầu vào "
        "(mặc định: data/evaluation/gold_questions.xlsx)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Đường dẫn tới file JSON đầu ra "
        "(mặc định: data/evaluation/questions.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input
    output_path = args.output

    WARNING_MESSAGES.clear()

    try:
        df = load_excel(input_path)

        print(f"Tổng số record trong Excel: {len(df)}")

        records = convert_questions(df)
        save_json(records, output_path)

        total_gold_ids = sum(len(item["gold_ids"]) for item in records)
        no_gold_count = sum(1 for item in records if not item["gold_ids"])

        print(f"Số record export JSON: {len(records)}")
        print(f"Số gold_ids được tạo: {total_gold_ids}")
        print(f"Số câu không có gold_ids: {no_gold_count}")
        print(f"Số warning: {len(WARNING_MESSAGES)}")
        print(f"Đường dẫn file JSON output: {output_path}")

        if WARNING_MESSAGES:
            print("\nCác warning đã phát hiện:")
            for msg in WARNING_MESSAGES:
                print(f"- {msg}")

    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
