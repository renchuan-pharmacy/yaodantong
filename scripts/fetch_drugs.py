#!/usr/bin/env python3
"""
自動下載健保署藥品資料CSV，轉換為JSON存入 data/drugs.json
"""
import requests
import json
import csv
import io
import chardet
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
    resp = requests.get(CSV_URL, headers=headers, timeout=60)
    resp.raise_for_status()
    
    # 自動偵測編碼
    detected = chardet.detect(resp.content)
    encoding = detected.get("encoding", "utf-8")
    print(f"偵測到編碼: {encoding}")
    
    try:
        text = resp.content.decode("utf-8-sig")
    except:
        try:
            text = resp.content.decode("big5", errors="replace")
        except:
            text = resp.content.decode(encoding, errors="replace")
    
    return text

def parse_csv(text):
    print("解析CSV資料...")
    reader = csv.DictReader(io.StringIO(text))
    drugs = []
    
    for row in reader:
        drug = {
            "code": row.get("藥品代號", "").strip(),
            "nameZh": row.get("藥品中文名稱", "").strip(),
            "nameEn": row.get("藥品英文名稱", "").strip(),
            "ingredient": row.get("成分", "").strip(),
            "dosageForm": row.get("劑型", "").strip(),
            "specAmount": row.get("規格量", "").strip(),
            "specUnit": row.get("規格單位", "").strip(),
            "type": row.get("單複方", "").strip(),
            "price": row.get("支付價", "").strip(),
            "validFrom": row.get("有效起日", "").strip(),
            "validTo": row.get("有效迄日", "").strip(),
            "manufacturer": row.get("製造廠名稱", "").strip(),
            "vendor": row.get("藥商", "").strip(),
            "dosageCategory": row.get("劑型", "").strip(),
            "category": row.get("藥品分類", "").strip(),
            "categoryName": row.get("分類分組名稱", "").strip(),
            "atcCode": row.get("ATC代碼", "").strip(),
            "paymentRule": row.get("給付規定章節", "").strip(),
        }
        # 過濾空資料
        if drug["code"] or drug["nameZh"]:
            drugs.append(drug)
    
    return drugs

def save_output(drugs):
    print(f"儲存 {len(drugs)} 筆藥品資料...")
    
    # 分批存檔（每批5000筆，方便查詢）
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(drugs, f, ensure_ascii=False, separators=(",", ":"))
    
    # 儲存 meta 資訊
    meta = {
        "total": len(drugs),
        "updatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "衛生福利部中央健康保險署",
        "resourceId": "A21030000I-E41001-001"
    }
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    print(f"完成！共 {len(drugs)} 筆，已存至 {OUTPUT_FILE}")
    print(f"Meta 資訊已存至 {META_FILE}")

if __name__ == "__main__":
    try:
        text = fetch_csv()
        drugs = parse_csv(text)
        save_output(drugs)
    except Exception as e:
        print(f"錯誤: {e}")
        raise
