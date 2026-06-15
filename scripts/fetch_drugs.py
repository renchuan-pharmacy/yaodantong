#!/usr/bin/env python3
"""
1. 讀取 pharmacy_db.json（藥局自建資料，有正確健保碼）
2. 下載健保署22萬筆
3. 合併並按【成分+劑型】分組
4. 輸出：
   - data/drugs.json（精簡索引，給API查詢）
   - data/drug_groups.json（分組，給AI生成說明）
   - data/meta.json
"""
import requests, json, csv, io, os, re
from datetime import datetime
from collections import defaultdict

CSV_URL = "https://info.nhi.gov.tw/api/iode0000s01/Dataset?rId=A21030000I-E41001-001"
PHARMACY_DB = "data/pharmacy_db.json"
OUTPUT_FILE = "data/drugs.json"
GROUPS_FILE = "data/drug_groups.json"
META_FILE   = "data/meta.json"

DOSAGE_TYPE_MAP = {
    '錠':'口服錠劑','膜衣錠':'口服錠劑','持續性錠':'口服錠劑','腸溶錠':'口服錠劑',
    '膠囊':'口服膠囊','硬膠囊':'口服膠囊','軟膠囊':'口服膠囊',
    '糖漿':'口服液劑','溶液':'口服液劑','懸浮液':'口服液劑','口服液':'口服液劑',
    '乳膏':'外用乳膏','軟膏':'外用軟膏','凝膠':'外用凝膠','gel':'外用凝膠',
    '乳液':'外用乳液','貼片':'外用貼片','貼布':'外用貼布',
    '眼藥水':'眼用液劑','眼用液':'眼用液劑','眼藥膏':'眼用軟膏',
    '耳藥水':'耳用液劑','耳用液':'耳用液劑','耳滴':'耳用液劑',
    '鼻噴':'鼻用噴霧','鼻用':'鼻用液劑',
    '注射液':'注射劑','注射用':'注射劑',
    '吸入劑':'吸入劑','吸入粉':'吸入劑','噴霧劑':'吸入劑',
    '栓劑':'塞劑/栓劑','塞劑':'塞劑/栓劑','suppositories':'塞劑/栓劑',
    '陰道':'陰道用藥',
    '散劑':'散劑/粉劑','粉劑':'散劑/粉劑',
    'lotion':'外用洗劑',
}

def normalize_dosage(form):
    if not form: return '口服錠劑'
    f = form.lower()
    for k, v in DOSAGE_TYPE_MAP.items():
        if k.lower() in f: return v
    return form[:10]

def normalize_ingredient(ing):
    if not ing: return ''
    # 取主成分，去掉劑量
    ing = re.sub(r'\s*[\d.]+\s*(mg|mcg|mg/gm|mg/ml|U|g|gm|%|unit|iu)[^\s,+/]*', '', ing, flags=re.IGNORECASE)
    for sep in ['+', '/', '&', '；', ';', '，']:
        if sep in ing:
            ing = ing.split(sep)[0]
    return ing.strip().upper()

def fetch_nhi_csv():
    print("下載健保署資料...")
    resp = requests.get(CSV_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
    resp.raise_for_status()
    print(f"下載完成 {len(resp.content)/1024/1024:.1f}MB")
    for enc in ["utf-8-sig","utf-8","big5","cp950"]:
        try: return resp.content.decode(enc)
        except: continue
    return resp.content.decode("utf-8", errors="replace")

def main():
    os.makedirs("data", exist_ok=True)

    # 讀藥局自建資料
    pharmacy_groups = {}
    if os.path.exists(PHARMACY_DB):
        print(f"讀取 {PHARMACY_DB}...")
        with open(PHARMACY_DB, encoding="utf-8") as f:
            pdb = json.load(f)
        pharmacy_drugs = pdb.get('drugs', [])
        print(f"  藥局資料：{len(pharmacy_drugs)} 筆")
        for d in pharmacy_drugs:
            ing_clean = normalize_ingredient(d.get('ingredient',''))
            dtype = d.get('dosageType','口服錠劑')
            gkey = f"{ing_clean}_{dtype}"
            if gkey not in pharmacy_groups:
                pharmacy_groups[gkey] = {
                    'ingredient': d.get('ingredient',''),
                    'ingredientClean': ing_clean,
                    'dosageType': dtype,
                    'category': d.get('category',''),
                    'source': 'pharmacy',
                    'items': []
                }
            pharmacy_groups[gkey]['items'].append({
                'code': d.get('nhiCode',''),
                'nameZh': d.get('nameZh',''),
                'nameEn': d.get('brandName',''),
                'spec': '',
                'price': '',
                'manufacturer': d.get('manufacturer',''),
                'atcCode': '',
            })

    # 下載健保署22萬筆
    text = fetch_nhi_csv()
    reader = csv.DictReader(io.StringIO(text))

    all_drugs = []
    nhi_groups = defaultdict(lambda: {
        'ingredient':'','ingredientClean':'','dosageType':'',
        'atcCode':'','source':'nhi','items':[]
    })

    for row in reader:
        name_zh   = row.get("藥品中文名稱","").strip()
        name_en   = row.get("藥品英文名稱","").strip()
        code      = row.get("藥品代號","").strip()
        ingredient= row.get("成分","").strip()
        dosage    = row.get("劑型","").strip()
        atc       = row.get("ATC代碼","").strip()
        price     = row.get("支付價","").strip()
        spec      = (row.get("規格量","")+' '+row.get("規格單位","")).strip()
        mfr       = row.get("製造廠名稱","").strip()
        valid_from= row.get("有效起日","").strip()

        if not (name_zh or code): continue

        dtype = normalize_dosage(dosage)
        ing_clean = normalize_ingredient(ingredient)

        all_drugs.append({
            "c": code, "z": name_zh, "e": name_en,
            "i": ingredient, "f": dosage, "ft": dtype,
            "s": spec, "p": price, "a": atc,
            "m": mfr, "t": valid_from,
        })

        if ing_clean and atc:
            gkey = f"{ing_clean}_{dtype}"
            g = nhi_groups[gkey]
            g['ingredient'] = ingredient
            g['ingredientClean'] = ing_clean
            g['dosageType'] = dtype
            g['atcCode'] = atc
            g['items'].append({
                'code': code, 'nameZh': name_zh, 'nameEn': name_en,
                'spec': spec, 'price': price, 'manufacturer': mfr,
                'atcCode': atc,
            })

    print(f"健保署：{len(all_drugs)} 筆，{len(nhi_groups)} 個分組")

    # 合併：藥局資料優先，健保署補齊
    merged_groups = dict(pharmacy_groups)
    for gkey, g in nhi_groups.items():
        if gkey not in merged_groups:
            merged_groups[gkey] = g
        else:
            # 藥局分組補上 atcCode
            if not merged_groups[gkey].get('atcCode') and g.get('atcCode'):
                merged_groups[gkey]['atcCode'] = g['atcCode']

    print(f"合併後：{len(merged_groups)} 個分組")

    # 儲存精簡索引
    json_str = json.dumps(all_drugs, ensure_ascii=False, separators=(",",":"))
    size_mb = len(json_str.encode())/1024/1024
    if size_mb > 95:
        half = len(all_drugs)//2
        with open("data/drugs_a.json","w",encoding="utf-8") as f:
            f.write(json.dumps(all_drugs[:half], ensure_ascii=False, separators=(",",":")))
        with open("data/drugs_b.json","w",encoding="utf-8") as f:
            f.write(json.dumps(all_drugs[half:], ensure_ascii=False, separators=(",",":")))
        idx = [{"c":d["c"],"z":d["z"],"e":d["e"],"ft":d["ft"],"a":d["a"]} for d in all_drugs]
        with open(OUTPUT_FILE,"w",encoding="utf-8") as f:
            f.write(json.dumps(idx, ensure_ascii=False, separators=(",",":")))
    else:
        with open(OUTPUT_FILE,"w",encoding="utf-8") as f:
            f.write(json_str)

    # 儲存分組
    with open(GROUPS_FILE,"w",encoding="utf-8") as f:
        json.dump(merged_groups, f, ensure_ascii=False, separators=(",",":"))

    # Meta
    meta = {
        "total": len(all_drugs),
        "groups": len(merged_groups),
        "pharmacyDrugs": len(pharmacy_drugs) if os.path.exists(PHARMACY_DB) else 0,
        "updatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "衛生福利部中央健康保險署 + 藥局自建資料"
    }
    with open(META_FILE,"w",encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！{len(all_drugs)} 筆，{len(merged_groups)} 個分組")

if __name__ == "__main__":
    main()
