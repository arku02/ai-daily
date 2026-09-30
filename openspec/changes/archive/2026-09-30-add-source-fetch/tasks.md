# 任務

## 1. 實作與驗證
- [x] 1.1 Item 格式與各來源轉換（HN、HF 模型、HF 論文、GitHub Trending、GitHub Search、RSS/Atom）；來源 R1；驗證 tests/test_fetch.py
- [x] 1.2 sources.toml 設定讀取與各來源過濾、停用來源不發請求；來源 R2；驗證 tests/test_fetch.py
- [x] 1.3 快照讀寫與 stars_delta／likes_delta 計算；來源 R3；驗證 tests/test_fetch.py
- [x] 1.4 網址正規化與跨來源合併；來源 R4；驗證 tests/test_fetch.py
- [x] 1.5 來源失敗隔離、退出碼與 token 遮蔽；來源 R5；驗證 tests/test_fetch.py
- [x] 1.6 fetch 指令、台北日期、輸出檔與狀態摘要；來源 R6；驗證 tests/test_fetch.py
- [x] 1.7 測試 fixture、HTTP 替身與測試檔登錄；來源 D1；驗證 tests/test_fetch.py
