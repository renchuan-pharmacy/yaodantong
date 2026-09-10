# 藥單通雙版本資料邊界

## 民眾版（GitHub Pages）

- 可搜尋：健保藥碼、中文名、英文名、成分、劑型、規格、製造廠、ATC 碼。
- 公開資料只來自健保署；店內 Excel 只用來篩選藥碼。
- 不公開：店內藥碼、即時庫存、成本、進貨紀錄、病人、處方或檢驗影像。
- 不提供：個別劑量、診斷、處方調整、療效保證、AI 自動保健品搭配。
- 是否有現貨、如何服用與交互作用，轉由藥師核對。

## 醫護版（不得部署在公開 GitHub Pages）

建議另建 Firebase Hosting + Google 登入的私有網站，並在伺服器端驗證允許名單。

- 角色：Owner、藥師、其他醫護；採最小權限。
- 內容：店內藥碼、即時庫存、批號／效期（若來源有提供）、缺藥註記。
- 所有讀取留下稽核紀錄；禁止瀏覽器快取；工作階段逾時需重新登入。
- 搜尋結果顯示資料時間，庫存採唯讀；調整庫存仍回原調劑系統操作。
- 病人與處方資料不得進入此靜態資料集，需另走有明確告知、同意、保存期限與刪除機制的流程。

## 匯入方式

```powershell
python -m pip install -r requirements-import.txt
python scripts/import_public_catalog.py --xls "C:\path\調劑庫存明細表.xls"
```

輸出只有 `data/public_catalog.json` 與不含明細的統計檔；原始 Excel 與 `private/` 已被 `.gitignore` 排除。
GitHub Actions 每週只以既有公開藥碼重新核對健保署資料，不需要、也不會取得店內 Excel。
