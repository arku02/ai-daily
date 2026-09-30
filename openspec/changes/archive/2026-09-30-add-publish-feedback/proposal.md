# 變更提案

## Why
第 2 步已產生每天的結構化早報內容（data/digest/<日期>.json），但使用者還看不到。使用者 2026-09-30 確認的交付方式：Telegram 每天推一則重點並附網頁連結，網頁放約 20 分鐘的深度版，並保留歷史；要有回饋按鈕，回饋存在另一個私人 repo，不跟公開的程式與網頁放在一起。

成功標準：一個指令產生可放上 GitHub Pages 的靜態網頁；一個指令推送 Telegram 重點訊息；使用者在 Telegram 或網頁上按的回饋，一個指令就能收回來、存到指定的私人資料夾；只接受使用者本人的回饋。

## What Changes
- `python -m ai_daily render`：把所有 data/digest/*.json 轉成 site/ 下的每日頁面與首頁（歷史列表），版面沿用 samples/2026-09-30.html。
- `python -m ai_daily push`：推送當天重點訊息到 Telegram，附網頁連結與「今天整體」的三個回饋按鈕；同一天不重複推送。
- 網頁上每則項目有三個回饋連結，點了會開啟 Telegram 並把回饋傳給 bot（Telegram deep link），不需要自己架伺服器。
- `python -m ai_daily collect`：從 Telegram 收回兩種回饋（訊息按鈕、網頁連結），只接受設定的 chat_id，寫入回饋資料夾（預設 feedback/，不進版控；第 4 步改成私人 repo 的 checkout）。
- 設定：`publish.toml` 放網址與 bot 使用者名稱；bot token 與 chat_id 放 .env。

採 full 模式：新增 Telegram 外部整合與回饋資料格式。

## Non-goals
- GitHub Actions 排程、Pages 部署、私人回饋 repo 的建立與推送（第 4 步）。
- 依回饋調整選題（等累積足夠資料後另開變更）。
- 共用 arxiv-digest 的 bot：兩邊都用 getUpdates 並以 offset 確認更新，共用會互相吃掉回饋，所以本專案使用新的 bot。

## Capabilities
### New Capabilities
- publish-feedback: 產生早報網頁、推送 Telegram 重點訊息，並收集使用者對整份早報與單則項目的回饋。
### Modified Capabilities
- 無。只讀取 llm-digest 的輸出。

## Impact
新增 `ai_daily/publish/`（render、telegram、push、collect）、`ai_daily/env.py`（統一讀 .env，llm.load_key 改用它）、`publish.toml`、`data/push/` 推送紀錄、`site/`（建置輸出，不進版控）、`feedback/`（本機預設回饋資料夾，不進版控）與測試。仍只用標準函式庫。需要使用者用 @BotFather 建立新 bot，並把 token 與 chat_id 寫入 .env。Telegram 只保留未確認的更新約 24 小時，collect 需要至少每天執行數次（第 4 步排程）。
