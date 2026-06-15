#!/usr/bin/env python3
"""
自動下載健保署藥品資料CSV，精簡後存入 data/drugs.json
目標：把120MB壓縮到20MB以下
"""
import requests
import json
import csv
import io
import gzip
import os
from datetime import datetime

CSV_URL = "https://info.nhi.gov.tw/api/iode0000s01/Dataset?rId=A21030000I-E41001-001"
OUTPUT_FILE = "data/drugs.json"
META_FILE = "data/meta.json"

def fetch_csv():
    print("下載健保署藥品資料...")
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; yaodantong-bot/1.0)",
        "Accept": "text/csv, application/json, */*"
    }
    resp = requests.get(CSV_URL, headers=headers, timeout=120)
    resp.raise_for_status()
    print(f"下載完成，大小: {len(resp.content)/1024/1024:.1f} MB")

    for enc in ["utf-8-sig", "utf-8", "big5", "cp950"]:
        try:
            return resp.content.decode(enc)
        except:
            continue
    return resp.content.decode("utf-8", errors="replace")

def parse_csv(text):
    print("解析CSV資料...")
    reader = csv.DictReader(io.StringIO(text))
    drugs = []

    for row in reader:
        # 只保留查詢必要的欄位，大幅縮小檔案
        name_zh = row.get("藥品中文名稱", "").strip()
        name_en = row.get("藥品英文名稱", "").strip()
        code = row.get("藥品代號", "").strip()
        if not (name_zh or name_en or code):
            continue

        drug = {
            "c": code,                                    # 藥品代號
            "z": name_zh,                                 # 中文名
            "e": name_en,                                 # 英文名
            "i": row.get("成分", "").strip(),             # 成分
            "f": row.get("劑型", "").strip(),             # 劑型
            "s": (row.get("規格量","").strip()+" "+row.get("規格單位","").strip()).strip(),  # 規格
            "p": row.get("支付價", "").strip(),           # 價格
            "a": row.get("ATC代碼", "").strip(),          # ATC碼
            "m": row.get("製造廠名稱", "").strip(),       # 製造廠
            "t": row.get("有效起日","").strip(),           # 有效起日
        }
        drugs.append(drug)

    print(f"解析完成：{len(drugs)} 筆")
    return drugs

def save_output(drugs):
    os.makedirs("data", exist_ok=True)

    # 序列化（無空白，最小化）
    json_str = json.dumps(drugs, ensure_ascii=False, separators=(",", ":"))
    size_mb = len(json_str.encode("utf-8")) / 1024 / 1024
    print(f"JSON 大小: {size_mb:.1f} MB")

    if size_mb > 95:
        # 還是太大就分批
        half = len(drugs) // 2
        with open("data/drugs_a.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(drugs[:half], ensure_ascii=False, separators=(",", ":")))
        with open("data/drugs_b.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(drugs[half:], ensure_ascii=False, separators=(",", ":")))
        # 輕量索引（只存代碼+名稱，供搜尋）
        index = [{"c":d["c"],"z":d["z"],"e":d["e"]} for d in drugs]
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps(index, ensure_ascii=False, separators=(",", ":")))
        print("已分割為 drugs_a.json + drugs_b.json + 索引 drugs.json")
    else:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"已存至 {OUTPUT_FILE}")

    meta = {
        "total": len(drugs),
        "updatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "衛生福利部中央健康保險署",
        "resourceId": "A21030000I-E41001-001",
        "sizeMb": round(size_mb, 1)
    }
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"完成！共 {len(drugs)} 筆")

if __name__ == "__main__":
    try:
        text = fetch_csv()
        drugs = parse_csv(text)
        save_output(drugs)
    except Exception as e:
        print(f"錯誤: {e}")
        raise
