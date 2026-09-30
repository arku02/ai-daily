# 任務

## 1. 實作與驗證
- [x] 1.1 daily workflow：build → deploy → notify，digest 失敗仍提交原始資料；來源 R1；驗證 tests/test_schedule.py
- [x] 1.2 collect workflow：取出私人 repo、FEEDBACK_DIR、提交回饋；來源 R2；驗證 tests/test_schedule.py
- [x] 1.3 共用 concurrency 群組；來源 R3；驗證 tests/test_schedule.py
- [x] 1.4 Secrets 名稱、profile.toml 執行時寫出、最小權限；來源 R4；驗證 tests/test_schedule.py
- [x] 1.5 各工作失敗時 Telegram 通知；來源 R5；驗證 tests/test_schedule.py
- [x] 1.6 提交步驟：bot 身分、指定路徑、無變更不提交、rebase 後推送；來源 R6；驗證 tests/test_schedule.py
- [x] 1.7 workflow 靜態檢查與測試檔登錄；來源 D1；驗證 tests/test_schedule.py
