# 變更提案

## Why
2026-09-30 第二次雲端執行（run 36722998982）：Gemini 3.8／3.7／3.5 Flash 壅塞，選題落到 gemini-3.5-flash-lite，結果 models 與 arch 章節都是 0 則，網頁只剩兩個章節。候選中其實有模型與論文（hf_models 20、hf_papers 25）。使用者要的四個欄位缺兩個，等於當天早報不完整。

## What Changes
- 選題提示加上「每個章節深度至少 2 則」。
- 驗證後若有章節深度為 0，再選一次並在提示中指出空的章節；取兩次中較完整者。

lite 模式：只修改既有 R2。

## Non-goals
- 用程式硬塞項目補滿章節（會失去選題判斷）。
- 更換模型清單（fix-llm-retry 已處理）。

## Capabilities
### New Capabilities
- 無。
### Modified Capabilities
- llm-digest: R2 增加每章節最少數量要求與空章節重選。

## Impact
ai_daily/digest/select.py、ai_daily/digest/run.py、tests/test_digest.py。最多多一次 API 呼叫。
