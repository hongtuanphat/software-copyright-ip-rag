"""Chuyển đổi tập câu hỏi gold Excel sang định dạng dev_set JSON cho Recall@K.

File này chỉ chuẩn hóa dữ liệu đầu vào từ Excel và sinh ra JSON theo schema:
[
  {
    "id": "...",
    "group": "...",
    "question": "...",
    "gold_ids": ["..."]
  }
]

Không tính toán Recall@K ở đây. Mục tiêu chỉ là đọc Excel, validate, ghép
`Dieu_ky_vong` + `Khoan_ky_vong` thành `gold_ids` theo chuẩn `Provision.provision_id`.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {
    "ID",
    "Nhom",
    "Cau_hoi",
    "Ma_van_ban_ky_vong",
    "Dieu_ky_vong",
    "Khoan_ky_vong",
}

HEADER_NORMALIZED = {
    "id": "ID",
    "nhom": "Nhom",
    "cau_hoi": "Cau_hoi",
    "ma_van_ban_ky_vong": "Ma_van_ban_ky_vong",
    "dieu_ky_vong": "Dieu_ky_vong",
    "khoan_ky_vong": "Khoan_ky_vong",
}

DEFAULT_INPUT = Path("data/evaluation/gold_questions.xlsx")
DEFAULT_OUTPUT = Path("data/evaluation/dev_set.json")
WARNING_MESSAGES: list[str] = []


def warn(message: str) -> None:
    """Ghi cảnh báo và lưu vào bộ đếm để in thống kê sau cùng."""
    print(f"WARNING: {message}")
    WARNING_MESSAGES.append(message)


def normalize_text(value: Any) -> str:
    """Chuẩn hóa chuỗi văn bản: xóa khoảng trắng đầu/cuối và convert NaN thành rỗng."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return text


def clean_token_list(raw_value: Any) -> list[str]:
    """Tách chuỗi như '3, 4, 5' hoặc '1;2' thành danh sách token hợp lệ."""
    text = normalize_text(raw_value)
    if not text:
        return []

    separators = r"[;,|\n]+"
    parts = re.split(separators, text)
    tokens: list[str] = []
    for part in parts:
        candidate = part.strip().replace(" ", "")
        if not candidate or candidate.lower() in {"nan", "none", "null"}:
            continue
        if candidate.endswith("."):
            candidate = candidate[:-1]
        if re.fullmatch(r"\d+\.0+", candidate):
            candidate = str(int(float(candidate)))
        tokens.append(candidate)
    return tokens


def parse_article_numbers(raw_value: Any) -> list[str]:
    """Chuẩn hóa các số Điều, giữ nguyên hậu tố chữ cái như 12a, 12b."""
    tokens = clean_token_list(raw_value)
    articles: list[str] = []
    for token in tokens:
        if not token:
            continue
        if token.lower() in {"nan", "none", "null"}:
            continue
        articles.append(token)
    return articles


def parse_clause_numbers(raw_value: Any) -> list[str]:
    """Chuẩn hóa các số Khoản. Nếu trường rỗng thì trả về []."""
    tokens = clean_token_list(raw_value)
    normalized: list[str] = []
    for token in tokens:
        if token:
            normalized.append(token)
    return normalized


def build_provision_id(law_code: str, article_no: str, clause_no: str | None = None) -> str:
    """Tạo provision_id theo quy tắc hiện có trong ingestion/chunker.py."""
    sanitized_code = str(law_code).strip().replace("/", "-")
    article = str(article_no).strip()
    if not article:
        raise ValueError("article_no không được rỗng khi tạo provision_id.")

    if clause_no is None:
        return f"{sanitized_code}_Art{article}"

    clause = str(clause_no).strip()
    if not clause or clause.lower() in {"nan", "none", "null"}:
        return f"{sanitized_code}_Art{article}"
    return f"{sanitized_code}_Art{article}_Kh{clause}"


def build_gold_ids(law_code: str, article_values: list[str], clause_values: list[str]) -> list[str]:
    """Ghép Điều + Khoản theo các quy tắc hợp lệ từ spec.

    Quy tắc hỗ trợ:
    - 1 Điều + N Khoản -> tạo N gold_ids với cùng Điều
    - N Điều + N Khoản -> ghép tương ứng theo vị trí
    - 1 hoặc nhiều Điều + không có Khoản -> tạo cấp Điều
    - Nhiều Điều + nhiều Khoản nhưng số lượng không tương ứng -> cảnh báo và bỏ qua
    """
    if not law_code:
        warn("Mã văn bản không hợp lệ; không thể tạo gold_ids.")
        return []

    article_values = [str(v).strip() for v in article_values if str(v).strip()]
    clause_values = [str(v).strip() for v in clause_values if str(v).strip()]

    if not article_values:
        warn("Dieu_ky_vong rỗng hoặc không hợp lệ; không thể tạo gold_ids.")
        return []

    if not clause_values:
        return [build_provision_id(law_code, article) for article in article_values]

    if len(article_values) == 1:
        return [
            build_provision_id(law_code, article_values[0], clause)
            for clause in clause_values
        ]

    if len(article_values) == len(clause_values):
        return [
            build_provision_id(law_code, article_values[i], clause_values[i])
            for i in range(len(article_values))
        ]

    warn(
        "Nhiều Điều và nhiều Khoản nhưng số lượng không khớp 1-1; "
        f"không tự suy đoán tích Descartes. Dieu_ky_vong={article_values}, Khoan_ky_vong={clause_values}."
    )
    return []


def strip_accents(value: str) -> str:
    """Bỏ dấu tiếng Việt để so khớp tên cột ổn định hơn."""
    if value is None:
        return ""
    mapping = {
        "à": "a", "á": "a", "ạ": "a", "ả": "a", "ã": "a",
        "â": "a", "ầ": "a", "ấ": "a", "ậ": "a", "ẩ": "a", "ẫ": "a",
        "ă": "a", "ằ": "a", "ắ": "a", "ặ": "a", "ẳ": "a", "ẵ": "a",
        "è": "e", "é": "e", "ẹ": "e", "ẻ": "e", "ẽ": "e",
        "ê": "e", "ề": "e", "ế": "e", "ệ": "e", "ể": "e", "ễ": "e",
        "ì": "i", "í": "i", "ị": "i", "ỉ": "i", "ĩ": "i",
        "ò": "o", "ó": "o", "ọ": "o", "ỏ": "o", "õ": "o",
        "ô": "o", "ồ": "o", "ố": "o", "ộ": "o", "ổ": "o", "ỗ": "o",
        "ơ": "o", "ờ": "o", "ớ": "o", "ợ": "o", "ở": "o", "ỡ": "o",
        "ù": "u", "ú": "u", "ụ": "u", "ủ": "u", "ũ": "u",
        "ư": "u", "ừ": "u", "ứ": "u", "ự": "u", "ử": "u", "ữ": "u",
        "ỳ": "y", "ý": "y", "ỵ": "y", "ỷ": "y", "ỹ": "y",
        "đ": "d",
    }
    text = str(value).strip()
    return "".join(mapping.get(ch, ch) for ch in text)


def normalize_column_name(value: Any) -> str:
    """Chuẩn hóa tên cột để so khớp theo tên nhập liệu Excel."""
    text = strip_accents(str(value or "")).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text


def detect_header_row(raw_df: pd.DataFrame) -> tuple[int, list[str]]:
    """Tìm hàng có chứa tiêu đề thực sự của bảng, bỏ qua metadata đầu file."""
    for idx, row in raw_df.iterrows():
        normalized = [normalize_column_name(cell) for cell in row.tolist()]
        found = {key: idx for key, idx in zip(normalized, range(len(normalized))) if key in HEADER_NORMALIZED}
        if not found:
            continue
        required_hits = 0
        for expected in HEADER_NORMALIZED:
            if expected in normalized:
                required_hits += 1
        if required_hits >= 4:
            columns = [str(cell) if pd.notna(cell) else "" for cell in row.tolist()]
            return idx, columns

    raise ValueError(
        "Không tìm thấy hàng header hợp lệ trong Excel. "
        "Vui lòng kiểm tra tên cột bắt buộc: ID, Nhom, Cau_hoi, Ma_van_ban_ky_vong, Dieu_ky_vong, Khoan_ky_vong."
    )


def load_excel(input_path: Path) -> pd.DataFrame:
    """Đọc file Excel và validate các cột bắt buộc."""
    if not input_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file Excel: {input_path}")

    try:
        raw_df = pd.read_excel(input_path, header=None, engine="openpyxl")
    except Exception as exc:  # pragma: no cover - chỉ để báo lỗi rõ ràng
        raise ValueError(f"Không đọc được file Excel {input_path}: {exc}") from exc

    header_row_index, header_values = detect_header_row(raw_df)
    data_df = raw_df.iloc[header_row_index + 1 :].copy()
    data_df.columns = header_values

    normalized_cols = [normalize_column_name(col) for col in data_df.columns]
    missing = [name for name in HEADER_NORMALIZED if name not in normalized_cols]
    if missing:
        raise ValueError(
            "Thiếu các cột bắt buộc trong file Excel: " + ", ".join(missing)
        )

    return data_df


def normalize_group(value: Any) -> str:
    """Giữ group dưới dạng string, tránh float 1.0."""
    text = normalize_text(value)
    if not text:
        return ""
    if re.fullmatch(r"\d+\.0+", text):
        return str(int(float(text)))
    return text


def convert_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Chuyển DataFrame Excel thành danh sách record JSON theo schema cuối cùng."""
    records_by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for row_index, row in df.iterrows():
        row_number = row_index + 2  # Excel line tính từ 2 (header row = 1)

        raw_id = normalize_text(row.get("ID"))
        if not raw_id:
            warn(f"Bỏ qua dòng {row_number}: thiếu ID.")
            continue

        row_id = str(raw_id)
        if row_id not in records_by_id:
            records_by_id[row_id] = {
                "id": row_id,
                "group": "",
                "question": "",
                "gold_ids": set(),
            }
            order.append(row_id)

        record = records_by_id[row_id]
        group_value = normalize_group(row.get("Nhom"))
        if not record["group"] and group_value:
            record["group"] = group_value

        question_value = normalize_text(row.get("Cau_hoi"))
        if question_value:
            if not record["question"]:
                record["question"] = question_value
            elif record["question"] != question_value:
                warn(
                    f"ID '{row_id}' có nhiều câu hỏi khác nhau trong Excel; "
                    "giữ câu hỏi đầu tiên và gom gold_ids lại."
                )

        law_code = normalize_text(row.get("Ma_van_ban_ky_vong"))
        if not law_code:
            warn(f"ID '{row_id}' thiếu Ma_van_ban_ky_vong; bỏ qua gold_ids ở dòng {row_number}.")
            continue

        article_values = parse_article_numbers(row.get("Dieu_ky_vong"))
        clause_values = parse_clause_numbers(row.get("Khoan_ky_vong"))

        if not article_values:
            warn(
                f"ID '{row_id}' có Mã văn bản '{law_code}' nhưng không có Dieu_ky_vong hợp lệ; "
                "không tạo gold_ids."
            )
            continue

        gold_ids = build_gold_ids(law_code, article_values, clause_values)
        for gold_id in gold_ids:
            record["gold_ids"].add(gold_id)

    output: list[dict[str, Any]] = []
    for row_id in order:
        record = records_by_id[row_id]
        question = normalize_text(record["question"])
        if not question:
            warn(f"ID '{row_id}' không có nội dung Cau_hoi hợp lệ; sẽ bỏ record này.")
            continue

        gold_ids = sorted(record["gold_ids"])
        output.append(
            {
                "id": str(record["id"]),
                "group": str(record["group"] or ""),
                "question": question,
                "gold_ids": gold_ids,
            }
        )

    return output


def save_json(records: list[dict[str, Any]], output_path: Path) -> None:
    """Lưu danh sách JSON theo UTF-8 và indent 2."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    """Phân tích tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        description="Chuyển đổi gold_questions.xlsx thành dev_set.json cho Recall@K."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Đường dẫn tới file Excel đầu vào (mặc định: data/evaluation/gold_questions.xlsx)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Đường dẫn tới file JSON đầu ra (mặc định: data/evaluation/dev_set.json)",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point chính của script."""
    args = parse_args()
    input_path = args.input
    output_path = args.output

    WARNING_MESSAGES.clear()

    try:
        df = load_excel(input_path)
        records = convert_rows(df)
        save_json(records, output_path)

        total_gold_ids = sum(len(item["gold_ids"]) for item in records)
        no_gold_count = sum(1 for item in records if not item["gold_ids"])

        print(f"Số dòng Excel đọc được: {len(df)}")
        print(f"Số câu hỏi được tạo: {len(records)}")
        print(f"Số gold_ids được tạo: {total_gold_ids}")
        print(f"Số câu không có gold_ids: {no_gold_count}")
        print(f"Số warning: {len(WARNING_MESSAGES)}")
        print(f"Đường dẫn file JSON output: {output_path}")

        if WARNING_MESSAGES:
            print("\nCác warning đã phát hiện:")
            for msg in WARNING_MESSAGES:
                print(f"- {msg}")

    except Exception as exc:  # pragma: no cover - để báo lỗi rõ ràng khi chạy CLI
        print(f"ERROR: {exc}", flush=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
