# AI Agent 早報

每天早上 9 點（台北時間）整理 AI Agent 圈的新聞、新模型、新架構與論文、GitHub 爆紅專案，產生繁體中文的深度早報網頁，並推送重點到 Telegram。

範例：[samples/2026-09-30.html](samples/2026-09-30.html)（手動整理，用來確認內容方向）

## 目前進度

| 步驟 | 內容 | 狀態 |
|---|---|---|
| 1 | 多來源抓取、去重、星數快照 | ✅ 已實作 |
| 2 | LLM 篩選、分類、寫摘要與「你可以怎麼用」 | ✅ 已實作 |
| 3 | 產生網頁、Telegram 推送、回饋按鈕 | ✅ 已實作 |
| 4 | GitHub Actions 每日排程、GitHub Pages 發布 | ⬜ |

## 安裝

需要 Python 3.12 以上，只用標準函式庫，不必安裝套件。

```bash
python -m venv .venv
```

## 使用

```bash
.venv\Scripts\python.exe -m ai_daily fetch                    # 抓今天（台北時間）的資料
.venv\Scripts\python.exe -m ai_daily fetch --date 2026-09-30  # 指定日期
```

```bash
.venv\Scripts\python.exe -m ai_daily digest                  # 用 Gemini 篩選並撰寫今天的早報內容
.venv\Scripts\python.exe -m ai_daily digest --dry-run        # 只看候選數與提示長度，不呼叫 API
```

fetch 的輸出：

- `data/raw/<日期>.json`：當天所有候選項目，已跨來源去重
- `data/snapshots/<日期>.json`：GitHub 星數與 HF 模型讚數，用來算隔天的成長量

第一次執行時沒有前一天的快照，所以 `stars_delta` 是 `null`，第二天起才會有數字。GitHub Trending 頁面本身提供的「今天 +N 星」存在 `stars_today`，第一天就有。

設定 `GITHUB_TOKEN` 環境變數可以提高 GitHub Search API 的查詢額度（未設定時每分鐘 10 次，目前 3 個查詢夠用）。

digest 的輸出是 `data/digest/<日期>.json`：今天只看三件事、四個章節（新聞、模型、架構與論文、GitHub）的深度項目與快速瀏覽、今天試一個。來源連結一律由程式從原始資料帶入，不採用模型寫的網址。

### Gemini 設定

1. 到 [Google AI Studio](https://aistudio.google.com/apikey) 建立 key（選免費方案）
2. 在專案根目錄的 `.env` 寫入 `GEMINI_API_KEY=你的key`（`.env` 不會被上傳）
3. 模型清單與各章節篇數在 [digest.toml](digest.toml)；額度用完時會自動換下一個模型
4. 讀者背景在 [profile.example.toml](profile.example.toml)；想改成自己的，複製成 `profile.toml` 再修改（不會被上傳）

免費方案的輸入可能被 Google 用於改進產品；送出的內容只有公開資料與 profile 的背景描述。每天約 6～7 次呼叫、80 秒左右。

## 發布與回饋

```bash
.venv\Scripts\python.exe -m ai_daily render                  # data/digest → site/（每天一頁 + 首頁）
.venv\Scripts\python.exe -m ai_daily push --dry-run          # 預覽 Telegram 訊息
.venv\Scripts\python.exe -m ai_daily push                    # 推送今天的重點（同一天不會重複送）
.venv\Scripts\python.exe -m ai_daily collect                 # 收回饋到 feedback/（或 FEEDBACK_DIR）
```

- `.env` 需要 `TELEGRAM_BOT_TOKEN` 與 `TELEGRAM_CHAT_ID`；bot 使用者名稱與網址在 [publish.toml](publish.toml)
- 本專案用自己的 bot，不和 arxiv-digest 共用：兩邊收回饋都會確認掉 Telegram 的更新，共用會互相吃掉
- 兩種回饋：Telegram 訊息下的按鈕評「今天整體」，網頁上每則的 👎👍⭐ 評「單則」（會開啟 Telegram 傳給 bot）
- 回饋存成 `feedback.jsonl`，每行一筆；bot 的「已記錄」回覆要等 collect 執行時才會出現
- Telegram 只保留約 24 小時的未確認更新，collect 要定期執行（第 4 步排程）

## 資料來源

設定在 [sources.toml](sources.toml)，每個來源都可以用 `enabled = false` 關閉。

| 來源 | 內容 | 2026-09-30 實測筆數 |
|---|---|---|
| `github_trending` | GitHub Trending（全部 + Python），解析網頁 | 23 |
| `github_search` | 近 14 天新建、依星數排序的 agent／mcp／llm repo | 81 |
| `hf_models` | Hugging Face 熱門模型（只留文字與多模態類） | 30 |
| `hf_papers` | Hugging Face Daily Papers（前一天，10 票以上） | 48 |
| `hn` | Hacker News 36 小時內、30 分以上的相關 story | 29 |
| `rss` | OpenAI、DeepMind、Google、HF、LangChain、GitHub、Simon Willison、TechCrunch、The Verge | 43 |

單一來源失敗不影響其他來源，失敗原因會記在輸出檔的 `sources` 欄位；全部失敗時退出碼為 1。

## 開發

本專案使用 [ai-dev-doc-template](.integration/GUIDE.md) 的規格流程，先讀 `.integration/PROJECT-RULES.md`。

```bash
node .integration/scripts/run-tests.mjs   # 離線測試，不連網
```
