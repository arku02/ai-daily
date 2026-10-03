# 任務

## 1. 實作與驗證
- [x] 1.1 網頁回饋連結加 data 屬性、內嵌送出程式、通行證存取、endpoint 過濾；來源 R3；驗證 tests/test_publish.py
- [x] 1.2 Cloudflare Worker：CORS、次數上限、通行證、格式與日期、項目存在、D1 寫入與讀取；來源 R8；驗證 tests/test_worker.py
- [x] 1.3 pass-link 指令：傳送通行證連結、缺金鑰退出 2、不輸出通行證；來源 R9；驗證 tests/test_publish.py
- [x] 1.4 collect 拉 Worker 評分、web_after、錯誤與金鑰遮蔽；來源 R10；驗證 tests/test_publish.py
- [x] 1.5 wrangler.toml、collect workflow Secret、測試檔登錄；來源 D1；驗證 tests/test_worker.py
- [x] 1.6 Secrets 清單加入 FEEDBACK_READ_KEY，只用在 collect；來源 R4；驗證 tests/test_schedule.py
