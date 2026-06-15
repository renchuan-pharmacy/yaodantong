#!/usr/bin/env python3
"""
自動用 Claude API 生成藥品說明，存入 data/drug_info/ 快取
每個藥只生成一次，之後直接讀快取
"""
import json
import os
import time
import requests
from pathlib import Path

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DRUG_LIST_FILE = "data/drug_list.json"
CACHE_DIR = Path("data/drug_info")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_TEMPLATE = """你是台灣的專業藥師，請用繁體中文為以下藥品提供完整說明。
藥品名稱：{drug_name}

請嚴格按照以下 JSON 格式回答，不要有任何其他文字：
{{
  "name": "藥品名稱（品牌名）",
  "en": "英文名稱",
  "icon": "一個最適合的emoji",
  "cat": "藥品分類・用途",
  "what": "這是什麼藥的白話說明（2-3句，讓一般民眾看懂）",
  "when": "服藥時間建議",
  "dose": "標準劑量說明",
  "warnings": ["注意事項1", "注意事項2", "注意事項3"],
  "emergency": ["需要立刻就醫的症狀1", "症狀2", "症狀3"],
  "sideEffects": ["副作用1", "副作用2", "副作用3"],
  "tips": ["藥師小叮嚀1", "叮嚀2", "叮嚀3"],
  "interactions": ["交互作用注意事項1", "注意事項2"],
  "supplements": [
    {{"icon": "emoji", "name": "保健品名稱", "reason": "推薦原因"}},
    {{"icon": "emoji", "name": "保健品名稱2", "reason": "推薦原因2"}}
  ]
}}"""

def generate_drug_info(drug_name):
    """呼叫 Claude API 生成藥品說明"""
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": PROMPT_TEMPLATE.format(drug_name=drug_name)}]
    }
    resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"].strip()
    # 清除可能的 markdown
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())

def get_cache_path(drug_name):
    safe = drug_name.replace("/", "_").replace(" ", "_")
    return CACHE_DIR / f"{safe}.json"

def main():
    with open(DRUG_LIST_FILE, encoding="utf-8") as f:
        drug_list = json.load(f)

    generated = 0
    skipped = 0
    failed = 0

    for drug_name in drug_list:
        cache_path = get_cache_path(drug_name)

        # 已有快取就跳過
        if cache_path.exists():
            print(f"⏭ 跳過（已有快取）：{drug_name}")
            skipped += 1
            continue

        print(f"🤖 生成中：{drug_name}")
        try:
            info = generate_drug_info(drug_name)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
            print(f"✅ 完成：{drug_name}")
            generated += 1
            time.sleep(1)  # 避免超過速率限制
        except Exception as e:
            print(f"❌ 失敗：{drug_name} - {e}")
            failed += 1
            time.sleep(2)

    # 產出合併索引
    all_drugs = {}
    for cache_file in CACHE_DIR.glob("*.json"):
        with open(cache_file, encoding="utf-8") as f:
            data = json.load(f)
        key = cache_file.stem.replace("_", "")
        all_drugs[key] = data

    with open("data/drug_db.json", "w", encoding="utf-8") as f:
        json.dump(all_drugs, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n完成！生成 {generated} 筆，跳過 {skipped} 筆，失敗 {failed} 筆")
    print(f"合併資料庫已存至 data/drug_db.json")

if __name__ == "__main__":
    main()
