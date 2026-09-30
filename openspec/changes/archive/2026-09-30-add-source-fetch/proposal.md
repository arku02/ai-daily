# 變更提案

## Why
使用者從事 AI Agent 開發（Python + LangGraph，做資料分析與自動化），想每天早上 9 點收到一份 AI Agent 早報，內容包含 Agent 新聞、新模型、新架構與論文、GitHub 爆紅專案，而且要能找到實際可用的工具。2026-09-30 手動整理的範例（samples/2026-09-30.html）經使用者確認，深度與「你可以怎麼用」的方向都正確。

要做成每天自動產生，第一步必須穩定取得原始資料。成功標準：一個指令就能從固定的幾個來源抓到當天的候選項目，存成統一格式；GitHub 的「爆紅」用星數成長判斷，而不是總星數；單一來源故障時，當天仍然有資料。

## What Changes
新增 `ai_daily` Python 套件與 `python -m ai_daily fetch` 指令。範圍：
- 來源：Hacker News（Algolia API）、Hugging Face 熱門模型與 Daily Papers、GitHub Trending 頁面、GitHub Search API（近期新建的 agent 相關 repo）、設定好的 RSS/Atom 來源。
- 各來源轉成統一的項目格式；以正規化網址跨來源去重合併。
- 每天存一份 GitHub 星數與 HF 模型讚數的快照，用來計算和前一份快照的成長量。
- 單一來源失敗不影響其他來源，失敗會記在輸出裡。
- 來源清單、關鍵字與門檻放在 `sources.toml`。

採用 full 模式：這是專案的第一個功能，會建立後續所有步驟依賴的資料格式。

## Non-goals
- LLM 篩選、摘要、分類，以及「排除融資與人事新聞」的判斷（第 2 步）。
- 產生網頁、Telegram 推送、回饋按鈕與私人回饋 repo（第 3 步）。
- GitHub Actions 排程與 GitHub Pages 發布（第 4 步）。
- X（Twitter）與 Reddit 來源。

## Capabilities
### New Capabilities
- source-fetch: 從多個來源抓取候選項目，統一格式、去重合併、計算成長量並輸出每日原始資料檔。
### Modified Capabilities
- 無（專案第一個變更）。

## Impact
新增 `ai_daily/` 套件、`sources.toml`、`data/raw/` 與 `data/snapshots/` 輸出目錄、`tests/` 離線測試與測試 fixture。只使用 Python 標準函式庫（3.12 以上，使用 tomllib），不新增第三方依賴。GitHub Trending 沒有官方 API，只能解析 HTML，頁面改版時這個來源會失敗；R5 的失敗隔離確保其他來源不受影響。
