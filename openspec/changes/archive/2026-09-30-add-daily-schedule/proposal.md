# 變更提案

## Why
第 1～3 步的指令都能在本機跑，但使用者要的是每天早上 9 點（台北時間）自動收到早報，電腦不用開著，而且以免費為主。網頁要能在 Telegram 訊息的「完整版」連結打開；回饋要定期收回並存進私人 repo ai-daily-feedback（使用者 2026-09-30 已建立 ai-daily 公開、ai-daily-feedback 私人兩個 repo）。

成功標準：每天自動完成「抓取 → 撰寫 → 網頁上線 → 推送」，推送時網頁已可打開；回饋每 6 小時收一次存進私人 repo；任何一步失敗時使用者會在 Telegram 收到通知；機密不出現在公開 repo。

## What Changes
- `.github/workflows/daily.yml`：每天 UTC 00:45（台北 08:45）執行 fetch、digest、render，把 data/ 提交回 ai-daily，部署 GitHub Pages，部署完成後才 push Telegram，並提交推送紀錄。可手動觸發。
- `.github/workflows/collect.yml`：每 6 小時執行 collect，把回饋提交到 ai-daily-feedback。
- 兩個流程共用同一個 concurrency 群組，不會同時呼叫 getUpdates 或同時提交。
- 機密放 GitHub Secrets：GEMINI_API_KEY、TELEGRAM_BOT_TOKEN、TELEGRAM_CHAT_ID、PROFILE_TOML（profile.toml 全文）、FEEDBACK_REPO_TOKEN（只能讀寫 ai-daily-feedback 的 fine-grained token）。
- 任何工作失敗時以 Telegram 通知使用者。
- 本機兩個 repo 的初次推送（需使用者同意）。

採 full 模式：新增排程、部署與機密設定。

## Non-goals
- 依回饋調整選題（等資料累積）。
- 改用付費的 Actions runner 或自架排程。
- 原始資料壓縮或清理舊資料（目前約每天 250 KB，一年約 90 MB，遠低於 repo 建議上限）。

## Capabilities
### New Capabilities
- daily-schedule: 在 GitHub Actions 上每日自動產生並發布早報、定期收回饋到私人 repo，失敗時通知使用者。
### Modified Capabilities
- 無。只呼叫既有指令。

## Impact
新增兩個 workflow 檔與測試。需要使用者在 GitHub 網頁操作：設定 5 個 Secrets、建立 fine-grained token、把 Pages 來源設為 GitHub Actions（Claude 不能代為輸入 token 或 key）。GitHub 排程在尖峰時段可能延遲數分鐘到數十分鐘，所以排在 08:45 開始，推送約在 9 點前後；無法保證準點。公開 repo 的 Actions 免費；私人 repo 不跑 Actions，只被寫入資料。
