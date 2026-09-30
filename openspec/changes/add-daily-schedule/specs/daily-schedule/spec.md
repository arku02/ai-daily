## Purpose
在 GitHub Actions 上每天自動執行 fetch、digest、render，部署 GitHub Pages 後推送 Telegram，並定期把 Telegram 回饋收進私人 repo；失敗時通知使用者，機密只存在 GitHub Secrets。

## ADDED Requirements

### Requirement: R1 - Daily pipeline order
daily workflow SHALL 在 cron `45 0 * * *`（UTC，台北 08:45）與手動觸發時執行，順序為：fetch → digest → render → 提交 data/ → 部署 Pages → push → 提交 data/push/。push SHALL 只在 Pages 部署成功後執行，確保訊息中的網址可開啟。digest 第一次失敗時 SHALL 等待 5 分鐘後重跑一次；重跑仍失敗時 SHALL 仍提交已抓到的原始資料，且 SHALL 不部署、不推送。

#### Scenario: Deploy before push
- **WHEN** daily workflow 執行
- **THEN** push 所在的工作依賴 Pages 部署工作完成

#### Scenario: Digest retried once
- **WHEN** digest 第一次以非零退出碼結束
- **THEN** 等待 300 秒後再執行一次 digest

#### Scenario: Digest fails
- **WHEN** digest 重跑後仍失敗
- **THEN** data/raw 與 data/snapshots 仍被提交，之後的部署與推送不執行

### Requirement: R2 - Feedback collection schedule
collect workflow SHALL 每 6 小時（cron `15 */6 * * *`）與手動觸發時執行，以 FEEDBACK_REPO_TOKEN 取出 arku02/ai-daily-feedback 到獨立資料夾，設定 FEEDBACK_DIR 指向該資料夾執行 collect，有變更時提交並推回該 repo。

#### Scenario: Feedback committed to private repo
- **WHEN** collect 收到新回饋
- **THEN** feedback.jsonl 與 state.json 的變更被提交到 ai-daily-feedback，不出現在 ai-daily

### Requirement: R3 - No overlapping runs
daily 與 collect workflow SHALL 使用同一個 concurrency 群組且不取消進行中的執行，避免同時呼叫 getUpdates 或同時提交。

#### Scenario: Collect during daily run
- **WHEN** collect 排程觸發時 daily 仍在執行
- **THEN** collect 等 daily 結束後才開始

### Requirement: R4 - Secrets handling
workflow SHALL 只從 GitHub Secrets 取得 GEMINI_API_KEY、TELEGRAM_BOT_TOKEN、TELEGRAM_CHAT_ID、PROFILE_TOML 與 FEEDBACK_REPO_TOKEN，以環境變數傳給指令；profile.toml SHALL 在執行時由 PROFILE_TOML 寫出且不被提交。workflow 的權限 SHALL 限縮為所需最小範圍（contents: write、pages: write、id-token: write）。

#### Scenario: Profile not committed
- **WHEN** daily workflow 提交 data/
- **THEN** 提交內容不含 profile.toml、.env 或 feedback/

### Requirement: R5 - Failure notification
任一工作失敗時，workflow SHALL 以 Telegram 傳送一則通知給 TELEGRAM_CHAT_ID，內容包含 workflow 名稱與該次執行的網址。

#### Scenario: Fetch fails
- **WHEN** daily workflow 的任何步驟失敗
- **THEN** 使用者在 Telegram 收到含執行網址的失敗通知

### Requirement: R6 - Safe commits
提交步驟 SHALL 以 github-actions[bot] 身分、只 add 指定路徑，沒有變更時不建立提交，推送前先 rebase 到遠端最新。

#### Scenario: Nothing changed
- **WHEN** 重跑同一天且 data/ 沒有變化
- **THEN** 不建立空提交，步驟成功
