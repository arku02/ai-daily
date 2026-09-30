# AI Agent 早報

每天早上 9 點（台北時間）整理 AI Agent 圈的新聞、新模型、新架構與論文、GitHub 爆紅專案，產生繁體中文的深度早報網頁，並推送重點到 Telegram。

範例：[samples/2026-09-30.html](samples/2026-09-30.html)（手動整理，用來確認內容方向）

## 目前進度

| 步驟 | 內容 | 狀態 |
|---|---|---|
| 1 | 多來源抓取、去重、星數快照 | ✅ 已實作 |
| 2 | LLM 篩選、分類、寫摘要與「你可以怎麼用」 | ⬜ |
| 3 | 產生網頁、Telegram 推送、回饋按鈕（回饋存私人 repo） | ⬜ |
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

輸出：

- `data/raw/<日期>.json`：當天所有候選項目，已跨來源去重
- `data/snapshots/<日期>.json`：GitHub 星數與 HF 模型讚數，用來算隔天的成長量

第一次執行時沒有前一天的快照，所以 `stars_delta` 是 `null`，第二天起才會有數字。GitHub Trending 頁面本身提供的「今天 +N 星」存在 `stars_today`，第一天就有。

設定 `GITHUB_TOKEN` 環境變數可以提高 GitHub Search API 的查詢額度（未設定時每分鐘 10 次，目前 3 個查詢夠用）。

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
