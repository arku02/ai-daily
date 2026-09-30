# 技術設計

## 已知事實
- GitHub Actions 執行 36719629687 的 Digest 日誌（使用者截圖，2026-09-30）：3.8-flash 503、3.5-flash 503、2.5-flash 404 not available to new users。
- 同日本機呼叫 gemini-3.8-flash 成功；`GET /v1beta/models` 列出 gemini-3.7-flash、gemini-3.5-flash-lite 等模型。

## 假設與待決問題
- 假設 503 壅塞通常在一兩分鐘內緩解（錯誤訊息自述 usually temporary）。無待決業務問題。

## 擬採方案與取捨
- generate_json 外層加上「輪次」：第一輪不等待，之後每輪前依 retry_waits 等待；回應 404 的模型記入 retired，之後輪次跳過；400、401、403 仍立即失敗。
- sleep 函式可注入，測試不真的等待。
- 每次呼叫（含重試）都計入 calls，維持 llm_calls 等於實際 API 請求數。

## 架構與資料影響
無新檔案；Gemini 建構子新增 retry_waits、sleep 參數，run.py 從 digest.toml 讀取。

## 驗證與回復
- 測試：503 後等待再成功、404 模型不重試、全數失敗仍丟錯、非可重試錯誤不等待。
- 回復：retry_waits 設為空陣列即回到原行為。
