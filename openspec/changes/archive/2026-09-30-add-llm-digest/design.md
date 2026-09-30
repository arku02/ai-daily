# 技術設計

## 已知事實
- source-fetch 已封存（openspec/specs/source-fetch），輸出 data/raw/<日期>.json；2026-09-30 實測 251 項。
- 2026-09-30 以使用者的 key 呼叫 `GET /v1beta/models` 成功，可用 44 個 generateContent 模型，包含 gemini-3.8-flash、gemini-3.5-flash、gemini-3.5-flash-lite、gemini-2.5-flash。
- 官方定價頁（2026-09-30 查閱）：上述 Flash 模型在免費方案輸入輸出皆免費；免費方案資料「用於改進產品」；免費方案不提供 Google Search grounding。
- 官方速率限制頁沒有列出免費方案的數字，只指向 AI Studio 的使用量頁面。
- 手動範例中，openai.com、cnbc.com 對非瀏覽器請求回應 403，所以原文補充抓取一定會有失敗。

## 假設與待決問題
- 假設免費方案每天至少允許十幾次請求；本設計每天約 6 次（選題 1 次 + 寫作 4～5 批），即使上限很低也有空間。
- 假設 JSON 模式（responseMimeType: application/json）在上述模型都可用；不使用 API 端的 schema 參數，改在程式內驗證，避免 schema 格式差異。
- 使用者背景目前以 2026-09-30 對話內容寫入 profile.example.toml；使用者可以自行建立 profile.toml 覆寫。
- 無待使用者決定的業務問題。

## 擬採方案與取捨
- **兩階段**：選題只看精簡清單（約 180 筆、每筆一行），省 token；寫作只對入選項目抓補充內容，再分章節批次寫。替代方案「每則各呼叫一次」要 17 次以上呼叫，容易撞到免費上限。
- **代號取代網址**：LLM 只看到 c1、c2 這類代號，不看網址，程式再把代號對回原始資料並帶入連結，所以不會出現編造的連結（R4）。
- **模型備援**：digest.toml 的 models 依序為 gemini-3.8-flash → gemini-3.5-flash → gemini-2.5-flash。429、5xx、404 就換下一個模型；每次呼叫各自從第一個開始，以便額度重置後回到最好的模型。
- **驗證與降級**：選題回應丟棄無效代號；寫作回應缺欄位時重試一次，仍不合格就降級為原始資料（fallback: true），確保當天一定有早報。
- **補充抓取**：GitHub README 用 raw.githubusercontent.com/<repo>/HEAD/README.md；HF 模型卡用 huggingface.co/<id>/raw/main/README.md；網頁用現有 http.get_text 後去除 script、style 與標籤。每則截斷到 3000 字元。
- **標準函式庫**：LLM 呼叫也用 urllib，沿用第 1 步做法，不引入 google-genai SDK。

## 架構與資料影響
```
ai_daily/digest/
  __init__.py
  candidates.py   # R1 候選準備與精簡清單
  llm.py          # R5 Gemini 客戶端、key 讀取、模型備援
  select.py       # R2 選題提示與驗證
  enrich.py       # R3 補充內容
  write.py        # R4 分批寫作、來源帶入、降級
  run.py          # R6 串接與輸出
digest.toml             # 上限、模型清單、補充字數
profile.example.toml    # 使用者背景範例（profile.toml 不進版控，R7）
data/digest/<日期>.json
tests/test_digest.py
```
cli.py 新增 digest 子指令。.gitignore 加入 profile.toml。

### Check: D1 - Offline tests
所有測試 SHALL 以假的 LLM 回應與替身 HTTP 執行，不發出網路請求、不需要真實 key；tests/test_digest.py SHALL 登錄在 workflow.config.json。

## 驗證與回復
- 自動測試：假 LLM 覆蓋選題驗證、備援、降級、來源帶入、key 遮蔽與 dry-run。
- 手動實機：用 2026-09-30 的原始資料跑一次真實 digest，檢查內容品質與呼叫次數，記錄在 review.md。
- 回復：只新增檔案與一個子指令；刪除 ai_daily/digest、digest.toml、profile.example.toml 並移除 cli 的 digest 子指令即可。
