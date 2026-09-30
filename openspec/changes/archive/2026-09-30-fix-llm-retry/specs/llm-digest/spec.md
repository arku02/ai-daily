## MODIFIED Requirements

### Requirement: R5 - Gemini client and key handling
LLM 客戶端 SHALL 從環境變數 GEMINI_API_KEY 讀取 key，沒有時讀取專案根目錄的 .env。沒有 key 時 digest SHALL 在任何 API 呼叫前以退出碼 2 結束，並提示在 .env 設定。請求 SHALL 要求 JSON 回應。遇到 429、5xx 或 404 時 SHALL 依 digest.toml 的模型清單改用下一個模型。整份清單都以 429、5xx 或連線錯誤失敗時，SHALL 依 digest.toml 的 retry_waits 等待後再嘗試一輪，回應 404 的模型 SHALL 不再重試；所有輪次都失敗時 digest SHALL 以退出碼 1 結束。key SHALL 不出現在任何輸出、錯誤訊息或檔案中。

#### Scenario: Missing key
- **WHEN** 環境變數與 .env 都沒有 GEMINI_API_KEY
- **THEN** 退出碼為 2，提示設定 .env，沒有 API 呼叫

#### Scenario: Quota fallback
- **WHEN** 第一個模型回應 429，第二個模型正常
- **THEN** 該次呼叫使用第二個模型完成，輸出的 models_used 含第二個模型

#### Scenario: Busy then retry
- **WHEN** retry_waits 為 [20, 60]，第一輪兩個模型都回應 503，等待 20 秒後第一個模型正常
- **THEN** 呼叫成功，期間等待 20 秒一次

#### Scenario: Retired model not retried
- **WHEN** 第一輪 m1 回應 503、m2 回應 404，等待後 m1 仍回應 503
- **THEN** 第二輪只呼叫 m1，不再呼叫 m2；所有輪次失敗後丟出錯誤

#### Scenario: Key masked
- **WHEN** API 錯誤訊息包含 key
- **THEN** 顯示的錯誤中 key 被替換成 ***
