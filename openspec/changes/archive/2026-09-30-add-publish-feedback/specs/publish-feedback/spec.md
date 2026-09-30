## Purpose
把每日結構化早報內容發布給使用者：產生可部署到 GitHub Pages 的靜態網頁與歷史首頁、推送 Telegram 重點訊息，並透過 Telegram 收集使用者對整份早報與單則項目的回饋，存到不公開的回饋資料夾。

## ADDED Requirements

### Requirement: R1 - Daily page
render SHALL 為 data/digest/ 下每個日期產生 site/<日期>.html，內容依序為：日期、今天只看三件事、章節導覽、news、models、arch、github 四個章節（深度項目含標題、標籤、指標、摘要、重點、你可以怎麼用、來源連結；快速瀏覽為表格）、今天試一個（try_one 為 null 時不顯示該區塊）。所有文字 SHALL 經 HTML 跳脫；連結 SHALL 只輸出 http 或 https 開頭的網址。fallback 為 true 的項目 SHALL 標示「原始資料」。頁面 SHALL 支援深色模式並在手機寬度可讀。

#### Scenario: Escaping and unsafe links
- **WHEN** 某項目標題含 <script>，某來源網址為 javascript:alert(1)
- **THEN** 頁面顯示跳脫後的文字，該來源不輸出連結

#### Scenario: Fallback marked
- **WHEN** 某深度項目 fallback 為 true
- **THEN** 該項目顯示「原始資料」標示

#### Scenario: No try one
- **WHEN** try_one 為 null
- **THEN** 頁面沒有今天試一個區塊，導覽也不列出

### Requirement: R2 - Index page
render SHALL 產生 site/index.html，顯示最新一天的日期、今天只看三件事與連結，以及所有日期的歷史列表（新到舊）。render SHALL 每次重建所有頁面；data/digest 沒有任何檔案時 SHALL 以退出碼 2 結束並提示先執行 digest。

#### Scenario: History list
- **WHEN** data/digest 有 2026-09-29 與 2026-09-30
- **THEN** index.html 以 2026-09-30 為最新，歷史列表依序為 09-30、09-29

### Requirement: R3 - Item feedback links
publish.toml 設定 bot_username 時，每個深度項目、快速瀏覽項目與今天試一個 SHALL 附三個回饋連結 https://t.me/<bot_username>?start=fb-<YYYYMMDD>-<ref>-<v>，v 為 0（沒興趣）、1（有用）、2（超有用）。未設定 bot_username 時 SHALL 不顯示回饋連結。

#### Scenario: Deep link format
- **WHEN** bot_username 為 ai_daily_bot，2026-09-30 的項目 c12
- **THEN** 「有用」連結為 https://t.me/ai_daily_bot?start=fb-20260930-c12-1

### Requirement: R4 - Telegram push
push SHALL 送出一則 HTML 格式的 Telegram 訊息，包含日期、今天只看三件事、每個章節深度項目的標題、今天試一個的標題（有的話）與當天網頁網址（publish.toml 的 base_url 加 <日期>.html），並附一列三個按鈕：👎 今天沒料、👍 有用、⭐ 很有收穫，callback data 為 day:<YYYYMMDD>:<v>。訊息 SHALL 不超過 4096 字元，超過時從章節標題的尾端刪減。成功後 SHALL 寫入 data/push/<日期>.json；該檔已存在時 SHALL 不重複推送並以退出碼 0 結束，除非加上 --force。--dry-run SHALL 印出訊息內容，不需要 token、不呼叫 Telegram、不寫檔。

#### Scenario: Message content
- **WHEN** 推送 2026-09-30，base_url 為 https://arku02.github.io/ai-daily/
- **THEN** 訊息含三件事、各章節標題與 https://arku02.github.io/ai-daily/2026-09-30.html，按鈕 callback data 為 day:20260930:0、day:20260930:1、day:20260930:2

#### Scenario: Already pushed
- **WHEN** data/push/2026-09-30.json 已存在時執行 push
- **THEN** 不呼叫 Telegram，退出碼 0，提示已推送過

#### Scenario: Too long
- **WHEN** 章節標題合計使訊息超過 4096 字元
- **THEN** 送出的訊息不超過 4096 字元，且仍含網頁網址與三件事

### Requirement: R5 - Telegram credentials
push 與 collect SHALL 從環境變數或 .env 讀取 TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID；非 dry-run 時缺少任一個 SHALL 在任何請求前以退出碼 2 結束並提示設定。token SHALL 不出現在任何輸出、錯誤訊息或檔案中。Telegram 回應 403 時 SHALL 提示先對 bot 按 Start。

#### Scenario: Missing token
- **WHEN** 沒有 TELEGRAM_BOT_TOKEN 時執行 push
- **THEN** 退出碼 2，提示在 .env 設定，沒有網路請求

#### Scenario: Token masked
- **WHEN** Telegram 錯誤訊息含 token
- **THEN** 顯示的錯誤中 token 被替換成 ***

### Requirement: R6 - Collect feedback
collect SHALL 以儲存的 offset 呼叫 getUpdates，處理兩種更新：callback data 為 day:<YYYYMMDD>:<v> 的按鈕（kind 為 day），以及文字為 /start fb-<YYYYMMDD>-<ref>-<v> 的訊息（kind 為 item）。只接受 chat id 等於 TELEGRAM_CHAT_ID 的更新，其他一律忽略。item 回饋 SHALL 從該日的 digest 檔找出項目的 source、id 與 title 一併記錄；找不到時仍記錄 ref 並標記 unknown_item 為 true。每筆回饋 SHALL 以一行 JSON 附加到回饋資料夾的 feedback.jsonl，欄位為 received_at、kind、date、value 與項目資訊。按鈕回饋 SHALL 以 answerCallbackQuery 回覆「已記錄」；item 回饋 SHALL 回覆一則確認訊息。寫入後 SHALL 把 offset 更新為最大 update_id + 1 並存到回饋資料夾的 state.json。格式不符的更新 SHALL 被略過但仍推進 offset。

#### Scenario: Day button
- **WHEN** 使用者按下 day:20260930:2
- **THEN** feedback.jsonl 新增 kind 為 day、date 為 2026-09-30、value 為 2 的一行，並回覆「已記錄」

#### Scenario: Item deep link
- **WHEN** 使用者從網頁點了 fb-20260930-c12-1，c12 在該日 digest 中是 NVIDIA/OpenShell
- **THEN** feedback.jsonl 新增 kind 為 item、value 為 1、id 為 NVIDIA/OpenShell 的一行

#### Scenario: Stranger ignored
- **WHEN** 另一個 chat id 傳了 /start fb-20260930-c12-2
- **THEN** 不寫入回饋、不回覆，但 offset 仍推進

### Requirement: R7 - Feedback location and outputs
回饋資料夾 SHALL 依序取環境變數 FEEDBACK_DIR、publish.toml 的 feedback.dir，預設為 feedback/；feedback/ 與 site/ SHALL 被 .gitignore 排除。collect 結束 SHALL 印出新增的回饋筆數。

#### Scenario: Env override
- **WHEN** FEEDBACK_DIR 設為另一個資料夾
- **THEN** feedback.jsonl 與 state.json 寫在該資料夾
