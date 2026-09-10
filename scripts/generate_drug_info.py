#!/usr/bin/env python3
"""
讀取 drug_groups.json，針對每個【成分+劑型】分組
用 Claude Haiku API 生成完整說明
輸出：data/drug_db.json
"""
import json, os, time, requests
from pathlib import Path

API_KEY   = os.environ.get("ANTHROPIC_API_KEY","")
GROUPS_FILE = "data/drug_groups.json"
CACHE_DIR   = Path("data/drug_info")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DOSAGE_HOW = {
    '口服錠劑': '整顆用水吞服，不可嚼碎或剝半（除非藥師說可以）',
    '口服膠囊': '整顆用水吞服，不可打開或嚼碎',
    '口服液劑': '用量杯或滴管量正確劑量，藥水搖勻再倒，服後漱口',
    '外用乳膏': '洗手後取少量薄塗患處，輕柔按摩至吸收，避免接觸眼睛和黏膜，使用後洗手',
    '外用軟膏': '洗手後取豌豆大小塗患處，不需要覆蓋（除非醫師指示），避免眼睛',
    '外用凝膠': '塗薄薄一層在患處，待乾後再穿衣服，避免日曬',
    '外用貼布': '貼在患處乾燥皮膚上，每片使用不超過12小時，不可貼在傷口或皮膚破損處',
    '外用貼片': '選擇皮膚完整處貼上，每次換貼不同部位，用過的貼片對折後丟棄',
    '眼用液劑': '步驟：1.洗手 2.頭後仰 3.輕拉下眼瞼 4.點1滴在眼瞼內 5.閉眼1分鐘 6.壓住內眼角。若需點多種眼藥水，間隔至少5分鐘',
    '眼用軟膏': '洗手後，將小量眼膏擠入下眼瞼，閉眼並輕輕轉動眼球，視力可能暫時模糊，建議睡前使用',
    '耳用液劑': '側躺患耳朝上，成人拉耳朵向後上方，滴入指定滴數，保持側躺5分鐘',
    '鼻用噴霧': '先輕輕擤鼻涕，頭微向前傾，將噴頭插入鼻孔，吸氣同時按壓噴頭，左手噴右鼻孔、右手噴左鼻孔',
    '注射劑': '步驟：1.從冰箱取出回溫30分鐘 2.選擇腹部/大腿/上臂外側輪流注射 3.捏起皮膚90度刺入 4.緩慢推入藥液 5.拔出後按壓10秒不揉 6.每次換注射點',
    '吸入劑': '步驟：1.搖勻（若需要）2.頭微後仰 3.緩慢吐氣 4.含住吸嘴 5.開始吸氣同時按壓 6.屏氣10秒 7.吸完後用清水漱口防口腔感染',
    '塞劑/栓劑': '步驟：1.洗手 2.側躺並彎曲膝蓋 3.將栓劑尖端朝前輕推入肛門約2公分 4.保持側躺15分鐘 5.使用後洗手。保存於冰箱（2-8°C）',
    '陰道用藥': '睡前使用：1.洗手 2.平躺彎膝 3.用給藥器將藥物推入陰道深處 4.使用後平躺至少30分鐘 5.療程中不可中斷',
}

PROMPT = """你是台灣的專業藥師小彌，用繁體中文說明以下藥品。

成分：{ingredient}
劑型：{dosage_type}
ATC碼：{atc_code}
台灣品牌：{brands}
使用方式重點：{how_to}

嚴格只回傳 JSON，不要其他文字：
{{
  "ingredientZh": "成分中文名稱",
  "icon": "最適合的emoji一個",
  "cat": "藥品分類・適應症（簡短）",
  "what": "白話說明這藥是做什麼用的（2-3句，讓不懂醫學的民眾看懂）",
  "when": "什麼時候用（飯前/飯後/睡前/需要時...）",
  "dose": "一般劑量說明",
  "howToUse": "詳細使用步驟（依劑型，分行說明）",
  "storage": "保存方式",
  "warnings": ["重要注意事項1", "注意事項2", "注意事項3"],
  "emergency": ["出現這個要馬上看醫生1", "症狀2", "症狀3"],
  "sideEffects": ["副作用1", "副作用2", "副作用3"],
  "tips": ["藥師小叮嚀1", "叮嚀2", "叮嚀3"],
  "interactions": ["交互作用1", "交互作用2"],
  "supplements": [
    {{"icon":"emoji", "name":"保健品名稱", "reason":"為什麼推薦"}},
    {{"icon":"emoji", "name":"保健品名稱2", "reason":"為什麼推薦2"}}
  ]
}}"""

def generate(ingredient, dosage_type, atc_code, brands):
    how_to = DOSAGE_HOW.get(dosage_type, '依醫師或藥師指示使用')
    brands_str = '、'.join(brands[:6]) if brands else '（健保藥品）'
    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1200,
        "messages": [{"role":"user","content": PROMPT.format(
            ingredient=ingredient, dosage_type=dosage_type,
            atc_code=atc_code, brands=brands_str, how_to=how_to
        )}]
    }
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key":API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
        json=body, timeout=30
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"): text = text[4:]
    return json.loads(text.strip())

def safe_key(k):
    import re
    return re.sub(r'[^\w\-]', '_', k)[:80]

def main():
    if not os.path.exists(GROUPS_FILE):
        print(f"找不到 {GROUPS_FILE}，請先跑 fetch_drugs.py")
        return

    with open(GROUPS_FILE, encoding="utf-8") as f:
        groups = json.load(f)

    total = len(groups)
    print(f"共 {total} 個分組需要生成說明")

    generated = skipped = failed = 0

    for gkey, gdata in groups.items():
        cache_path = CACHE_DIR / f"{safe_key(gkey)}.json"

        if cache_path.exists():
            skipped += 1
            if skipped % 100 == 0:
                print(f"⏭ 跳過 {skipped}/{total}...")
            continue

        ingredient  = gdata.get('ingredient', gkey)
        dosage_type = gdata.get('dosageType', '口服錠劑')
        atc_code    = gdata.get('atcCode', '')
        items       = gdata.get('items', [])
        brands = list(dict.fromkeys([
            it.get('nameZh','') or it.get('nameEn','')
            for it in items if it.get('nameZh') or it.get('nameEn')
        ]))

        print(f"🤖 [{generated+skipped+failed+1}/{total}] {ingredient} [{dosage_type}] {len(items)}筆")

        try:
            info = generate(ingredient, dosage_type, atc_code, brands)

            # 加入品牌清單（含健保碼）
            info['groupKey']    = gkey
            info['ingredient']  = ingredient
            info['dosageType']  = dosage_type
            info['atcCode']     = atc_code
            info['source']      = gdata.get('source','nhi')
            info['brands'] = [{
                'nhiCode':     it.get('code',''),
                'nameZh':      it.get('nameZh',''),
                'nameEn':      it.get('nameEn',''),
                'spec':        it.get('spec',''),
                'price':       it.get('price',''),
                'manufacturer':it.get('manufacturer',''),
            } for it in items[:30]]

            with open(cache_path,"w",encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)

            generated += 1
            time.sleep(0.8)

        except Exception as e:
            print(f"  ❌ 失敗：{e}")
            failed += 1
            time.sleep(2)

    # 合併所有快取成 drug_db.json
    print("\n合併快取...")
    db = {}
    for cache_file in CACHE_DIR.glob("*.json"):
        try:
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
            db[cache_file.stem] = data
        except: pass

    with open("data/drug_db.json","w",encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, separators=(",",":"))

    print(f"\n✅ 完成！生成 {generated}，跳過 {skipped}，失敗 {failed}")
    print(f"   drug_db.json 共 {len(db)} 個分組")

if __name__ == "__main__":
    main()
