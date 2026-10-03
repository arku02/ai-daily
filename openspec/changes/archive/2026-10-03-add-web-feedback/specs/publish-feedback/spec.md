## MODIFIED Requirements

### Requirement: R3 - Item feedback links
publish.toml 設定 bot_username 時，每個深度項目、快速瀏覽項目與今天試一個 SHALL 附三個回饋連結 https://t.me/<bot_username>?start=fb-<YYYYMMDD>-<ref>-<v>，v 為 0（沒興趣）、1（有用）、2（超有用）。未設定 bot_username 時 SHALL 不顯示回饋連結。同時設定 bot_username 與 publish.toml 的 feedback.endpoint（https 網址）時，每個回饋連結 SHALL 另帶 data-day、data-ref、data-v 屬性，每一頁（含首頁）SHALL 內嵌送出程式：網址為 #k=<通行證> 時把通行證存進瀏覽器並從網址移除；瀏覽器有通行證時，按回饋連結 SHALL 不開啟 Telegram，改以 POST <endpoint>/feedback 送出 date、ref、value 與通行證，成功後標示該選項已選並記住選擇，失敗時顯示沒送出，回應 401 時移除通行證並提示重新打開通行證連結；瀏覽器沒有通行證時 SHALL 照舊開啟 deep link。feedback.endpoint 為空、不是 https 網址或未設定 bot_username 時 SHALL 不輸出送出程式與 data 屬性。

#### Scenario: Deep link format
- **WHEN** bot_username 為 ai_daily_bot，2026-09-30 的項目 c12
- **THEN** 「有用」連結為 https://t.me/ai_daily_bot?start=fb-20260930-c12-1

#### Scenario: Direct mode markup
- **WHEN** bot_username 為 ai_daily_bot，feedback.endpoint 為 https://fb.example.workers.dev
- **THEN** c12 的「有用」連結仍指向 deep link，並帶 data-day="2026-09-30"、data-ref="c12"、data-v="1"；頁面與首頁都含送出程式與該 endpoint

#### Scenario: Endpoint not https
- **WHEN** feedback.endpoint 為空或為 javascript:alert(1)
- **THEN** 頁面沒有送出程式與 data-ref 屬性

## ADDED Requirements

### Requirement: R8 - Web feedback endpoint
worker/ 的 Cloudflare Worker SHALL 提供 /feedback：
- OPTIONS SHALL 回 204 與 CORS 標頭，允許的來源只有 ALLOWED_ORIGIN；POST 回應也 SHALL 帶相同 CORS 標頭。
- POST SHALL 依序檢查：同一 IP 每 60 秒超過 20 次回 429；Authorization 不是 Bearer <WEB_KEY>（以固定時間比較）或 WEB_KEY 未設定回 401；內容超過 1024 bytes 回 413；date 不是 YYYY-MM-DD 的真實日期、不在 UTC 今天往前 60 天到往後 1 天內、ref 不符 c 加 1～4 位數字、value 不是整數 0、1、2 時回 400；SITE_URL/<date>.html 無法取得回 503；該頁不含 data-ref="<ref>" 回 404。全部通過時 SHALL 寫入 D1 一列（id 自動遞增、received_at 為 UTC ISO 時間、date、ref、value）並回 200。
- GET SHALL 要求 Authorization 為 Bearer <READ_KEY>，否則回 401；SHALL 回傳 id 大於 after 參數（預設 0）的列，依 id 由小到大，最多 500 列。
- 其他路徑 SHALL 回 404，其他方法 SHALL 回 405。

#### Scenario: Valid rating stored
- **WHEN** 帶正確通行證 POST {"date":"2026-09-30","ref":"c12","value":1}，該頁含 data-ref="c12"
- **THEN** 回 200，D1 多一列 date 2026-09-30、ref c12、value 1

#### Scenario: No pass rejected
- **WHEN** 沒有 Authorization 或通行證錯誤
- **THEN** 回 401，D1 沒有新增

#### Scenario: Bad content rejected
- **WHEN** value 為 5、ref 為 x1、或 date 為 2026-02-30
- **THEN** 回 400，D1 沒有新增

#### Scenario: Unknown item rejected
- **WHEN** 該日頁面不含 data-ref="c999" 而 POST ref 為 c999
- **THEN** 回 404，D1 沒有新增

#### Scenario: Rate limited
- **WHEN** 同一 IP 在 60 秒內第 21 次 POST
- **THEN** 回 429，D1 沒有新增

#### Scenario: Read with read key
- **WHEN** D1 有 id 1～3，以 READ_KEY GET /feedback?after=1
- **THEN** 回傳 id 2、3；以 WEB_KEY GET 回 401

### Requirement: R9 - Pass link
pass-link 指令 SHALL 從環境變數或 .env 讀取 FEEDBACK_WEB_KEY 與 Telegram 設定，以 sendMessage 傳送 <base_url>index.html#k=<FEEDBACK_WEB_KEY> 與使用說明給 TELEGRAM_CHAT_ID，並關閉連結預覽。缺少 FEEDBACK_WEB_KEY 時 SHALL 在任何請求前以退出碼 2 結束並提示設定。通行證 SHALL 不出現在終端輸出或錯誤訊息中。

#### Scenario: Link sent
- **WHEN** FEEDBACK_WEB_KEY 為 abcDEF123456789xyz，base_url 為 https://arku02.github.io/ai-daily/
- **THEN** Telegram 訊息含 https://arku02.github.io/ai-daily/index.html#k=abcDEF123456789xyz，終端輸出不含該值

#### Scenario: Missing pass key
- **WHEN** 沒有 FEEDBACK_WEB_KEY
- **THEN** 退出碼 2，提示在 .env 設定，沒有網路請求

### Requirement: R10 - Collect web feedback
publish.toml 的 feedback.endpoint 有值時，collect SHALL 在處理 Telegram 更新後，以 Bearer <FEEDBACK_READ_KEY>（環境變數或 .env）分頁 GET <endpoint>/feedback?after=<web_after>，web_after 取自回饋資料夾 state.json，預設 0。每列 SHALL 以 kind item、via web、received_at 取 Worker 記錄的時間，附加到 feedback.jsonl，項目資訊與 unknown_item 規則同 R6；格式不符的列 SHALL 略過但仍推進 web_after。完成後 SHALL 把 web_after 更新為最大 id 並保留 state.json 其他欄位，並印出網頁回饋筆數。endpoint 有值但缺 FEEDBACK_READ_KEY，或 Worker 請求失敗時，Telegram 回饋 SHALL 照常寫入，collect SHALL 以退出碼 1 結束；錯誤訊息 SHALL 不含金鑰。feedback.endpoint 為空時 SHALL 不呼叫 Worker。

#### Scenario: Web ratings collected
- **WHEN** Worker 回傳 id 4 的 {"date":"2026-09-30","ref":"c12","value":2}
- **THEN** feedback.jsonl 新增 kind item、via web、id 為 NVIDIA/OpenShell、value 2 的一行，state.json 的 web_after 為 4，offset 保留

#### Scenario: Missing read key
- **WHEN** endpoint 有值、沒有 FEEDBACK_READ_KEY，Telegram 有一筆回饋
- **THEN** Telegram 回饋寫入，退出碼 1，提示設定 FEEDBACK_READ_KEY

#### Scenario: Worker error masked
- **WHEN** Worker 回應 500，錯誤內容含讀取金鑰
- **THEN** 退出碼 1，顯示的錯誤中金鑰被替換成 ***
