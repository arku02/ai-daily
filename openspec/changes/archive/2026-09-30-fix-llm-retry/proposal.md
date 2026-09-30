# 變更提案

## Why
2026-09-30 第一次在 GitHub Actions 手動執行 daily，digest 失敗：gemini-3.8-flash 與 gemini-3.5-flash 都回應 503「This model is currently experiencing high demand」，備援的 gemini-2.5-flash 回應 404「no longer available to new users」。本機同一把 key 幾分鐘後呼叫正常，代表是暫時性壅塞加上備援清單過時。每天只跑一次的早報不能因為一時的 503 就整天沒有。

## What Changes
- Gemini 客戶端：整份模型清單都因 429／5xx／連線錯誤失敗時，依 retry_waits（預設 20、60 秒）等待後再試；404 的模型在之後的輪次跳過。
- digest.toml：模型清單改為 gemini-3.8-flash → gemini-3.7-flash → gemini-3.5-flash → gemini-3.5-flash-lite（2026-09-30 定價頁列為免費，且 models 清單可用），移除 gemini-2.5-flash；新增 retry_waits。
- daily workflow：digest 失敗時等 5 分鐘再整個重跑一次（屬於 add-daily-schedule 仍在進行的變更，於該變更一併記錄）。

lite 模式：只修改既有 R5 的重試行為與設定。

## Non-goals
- 改用付費方案或其他 LLM 供應商。
- 模型清單自動偵測。

## Capabilities
### New Capabilities
- 無。
### Modified Capabilities
- llm-digest: R5 增加整輪重試與 404 模型跳過；其餘需求不變。

## Impact
ai_daily/digest/llm.py、ai_daily/digest/run.py（傳入 retry_waits）、digest.toml、tests/test_digest.py。最壞情況下 digest 會多等約 80 秒。
