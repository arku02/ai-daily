# 變更提案

## Why
網頁上每則的 👎👍⭐ 目前是 Telegram deep link（publish-feedback R3），每按一次都會跳離網頁、開啟 Telegram，使用者 2026-10-03 反映「很麻煩也很影響閱讀」。原因是 GitHub Pages 只放靜態檔案，沒有地方接收評分。

使用者 2026-10-03 選擇「方案 1＋通行證」：用免費的 Cloudflare Worker 接收網頁評分，並要求只有持有通行證的瀏覽器才能送出，讓公開網址的亂送風險接近現在 Telegram 只收自己 chat id 的程度。

成功標準：已設定通行證的瀏覽器按評分時留在原頁、按鈕顯示已記錄；評分照常由 collect 寫入私人 repo 的 feedback.jsonl；沒有通行證的請求一律被拒；未設定通行證的瀏覽器仍可用原本的 Telegram 連結評分，不會遺失回饋。

## What Changes
- `worker/`：Cloudflare Worker 與 D1 資料表。POST /feedback 收評分（通行證、格式、日期範圍、項目存在、每分鐘次數上限），GET /feedback 供 collect 以另一把讀取金鑰拉回。
- 網頁：publish.toml 設定 `feedback.endpoint` 時，評分連結帶上日期、項目與數值；頁面程式在有通行證時改為直接送到 Worker，不跳轉；網址 `#k=<通行證>` 會被存進瀏覽器並從網址移除。沒有通行證時維持原本的 deep link。
- 新指令 `pass-link`：用 Telegram 把通行證連結傳給使用者，在手機、電腦各打開一次即可。
- collect：除了 Telegram，也從 Worker 拉網頁評分，寫入同一個 feedback.jsonl，進度存在 state.json。
- collect workflow 增加 `FEEDBACK_READ_KEY` Secret。

採 full 模式：新增外部服務、公開端點與兩把機密。

## Non-goals
- 移除 Telegram deep link（保留為沒有通行證時的備援）。
- Telegram 訊息上的「今天整體」按鈕（不變）。
- 依回饋調整選題。
- 評分的撤回或修改介面（同一則多次評分照舊都保留，分析時取最新一筆）。

## Capabilities
### New Capabilities
- 無。網頁回饋仍屬於發布與回饋能力。
### Modified Capabilities
- publish-feedback: 修改 R3（評分連結增加直接送出模式）；新增 R8（Worker 端點）、R9（通行證連結）、R10（collect 拉網頁評分）。
- daily-schedule: 修改 R4（Secrets 清單加入 FEEDBACK_READ_KEY，只用在 collect workflow）。

## Impact
新增 worker/ 與 ai_daily 的網頁程式、collect 與 CLI 修改、collect workflow 一個環境變數。需要使用者操作：註冊 Cloudflare 帳號並在瀏覽器完成 `wrangler login`、在 GitHub 新增 `FEEDBACK_READ_KEY` Secret（Claude 不能代為登入或在網頁輸入金鑰）。Cloudflare 免費額度（Workers 每天 10 萬次請求、D1 每天 10 萬次寫入）遠高於個人用量。風險：Worker 或 Cloudflare 故障時網頁評分送不出去，頁面會顯示「沒送出」，使用者仍可改用 Telegram；通行證外流時任何人都能送評分，處理方式是換一組新通行證並重新傳送連結。
