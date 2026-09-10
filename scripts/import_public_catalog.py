#!/usr/bin/env python3
"""Build the public Yaodantong catalog without publishing private inventory data.

The pharmacy XLS is used only as a list of drug codes. Internal medicine numbers,
stock quantities, and the XLS text fields are never written to public output.
Public descriptions are joined from the NHI open-data CSV.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import requests


NHI_CSV_URL = (
    "https://info.nhi.gov.tw/api/iode0000s01/Dataset"
    "?rId=A21030000I-E41001-001"
)
NHI_SEARCH_URL = "https://info.nhi.gov.tw/INAE3000"
CODE_PATTERN = re.compile(r"^[A-Z0-9]{10}$")


def roc_date_today() -> str:
    today = date.today()
    return f"{today.year - 1911:03d}{today.month:02d}{today.day:02d}"


def clean(value: object) -> str:
    return str(value or "").replace("\u0000", "").strip()


def load_inventory_codes(path: Path) -> list[str]:
    import xlrd

    sheet = xlrd.open_workbook(str(path), on_demand=True).sheet_by_index(0)
    headers = [clean(sheet.cell_value(0, col)).lower() for col in range(sheet.ncols)]
    try:
        code_col = headers.index("drugid")
    except ValueError as exc:
        raise ValueError("找不到 drugid 欄位，請確認輸入的是調劑庫存明細表。") from exc

    codes: list[str] = []
    seen: set[str] = set()
    for row in range(1, sheet.nrows):
        code = clean(sheet.cell_value(row, code_col)).upper()
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def load_public_codes(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    return list(dict.fromkeys(clean(item.get("code")).upper() for item in items if clean(item.get("code"))))


def fetch_official_rows() -> list[dict[str, str]]:
    response = requests.get(
        NHI_CSV_URL,
        headers={"User-Agent": "Yaodantong public catalog builder/1.0"},
        timeout=180,
    )
    response.raise_for_status()
    text = response.content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def is_active(row: dict[str, str], today_roc: str) -> bool:
    start = clean(row.get("有效起日"))
    end = clean(row.get("有效迄日"))
    return (not start or start <= today_roc) and (not end or end >= today_roc)


def latest_row(rows: list[dict[str, str]], today_roc: str) -> dict[str, str]:
    active = [row for row in rows if is_active(row, today_roc)]
    candidates = active or rows
    return max(candidates, key=lambda row: clean(row.get("有效起日")))


def make_item(row: dict[str, str], today_roc: str) -> dict[str, object]:
    spec_parts = [clean(row.get("規格量")), clean(row.get("規格單位"))]
    return {
        "code": clean(row.get("藥品代號")),
        "nameZh": clean(row.get("藥品中文名稱")),
        "nameEn": clean(row.get("藥品英文名稱")),
        "ingredient": clean(row.get("成分")),
        "dosageForm": clean(row.get("劑型")),
        "spec": " ".join(part for part in spec_parts if part),
        "manufacturer": clean(row.get("製造廠名稱")) or clean(row.get("藥商")),
        "atcCode": clean(row.get("ATC代碼")),
        "effectiveFrom": clean(row.get("有效起日")),
        "effectiveUntil": clean(row.get("有效迄日")),
        "currentlyCovered": is_active(row, today_roc),
        "licenseUrl": clean(row.get("藥品代碼超連結")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--xls", type=Path)
    source.add_argument(
        "--codes-json",
        type=Path,
        help="Refresh an existing public catalog without needing the private XLS.",
    )
    parser.add_argument("--output", default=Path("data/public_catalog.json"), type=Path)
    parser.add_argument(
        "--meta-output", default=Path("data/public_catalog_meta.json"), type=Path
    )
    args = parser.parse_args()

    inventory_codes = (
        load_inventory_codes(args.xls)
        if args.xls
        else load_public_codes(args.codes_json)
    )
    accepted_codes = {code for code in inventory_codes if CODE_PATTERN.fullmatch(code)}
    today_roc = roc_date_today()

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in fetch_official_rows():
        code = clean(row.get("藥品代號")).upper()
        if code in accepted_codes:
            grouped.setdefault(code, []).append(row)

    items = [make_item(latest_row(grouped[code], today_roc), today_roc) for code in sorted(grouped)]
    items.sort(key=lambda item: (str(item["nameZh"]), str(item["nameEn"]), str(item["code"])))

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    public_payload = {
        "schemaVersion": "2026-09-10.v1",
        "generatedAt": generated_at,
        "sourceName": "衛生福利部中央健康保險署－健保用藥品項",
        "sourceUrl": NHI_SEARCH_URL,
        "notice": "本資料僅供藥品辨識與一般資訊查詢，不代表本店即時庫存，亦不取代醫師診斷或藥師用藥指導。",
        "items": items,
    }
    public_meta = {
        "generatedAt": generated_at,
        "inventoryRows": len(inventory_codes),
        "validNhiCodes": len(accepted_codes),
        "publishedItems": len(items),
        "excludedOrUnmatched": len(inventory_codes) - len(items),
        "privateFieldsPublished": [],
        "sourceUrl": NHI_SEARCH_URL,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(public_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    args.meta_output.write_text(
        json.dumps(public_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(public_meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
