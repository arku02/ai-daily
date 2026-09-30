# 技術設計

## 已知事實
- llm-digest 已封存，輸出 data/digest/<日期>.json；欄位見 openspec/specs/llm-digest。
- samples/2026-09-30.html 是使用者確認過的版面（2026-09-30，回饋 1A 2A）。
- arxiv-digest 的 notifier.py 以 getUpdates 帶 offset 確認更新（第 129～134 行），與本專案共用 bot 會互相確認掉對方的更新。
- Telegram Bot API：訊息上限 4096 字元；callback_data 上限 64 bytes；deep link 的 start 參數限 64 字元、只能用 A–Z a–z 0–9 _ -；未確認的更新保留約 24 小時。
- 使用者已有 Telegram，並熟悉 @BotFather 建 bot 的流程（arxiv-digest README 的設定步驟）。

## 假設與待決問題
- 假設 GitHub Pages 網址為 https://arku02.github.io/ai-daily/（repo 名稱已於 2026-09-30 確認為 ai-daily）；可在 publish.toml 修改。
- 網頁回饋用 deep link：點下去會開啟 Telegram 對話並送出 /start 參數。部分 Telegram 版本在既有對話中需要再按一次「開始」，這是 Telegram 的行為，無法由本專案控制。
- 新 bot 的使用者名稱在使用者建立後填入 publish.toml；未填時網頁不顯示回饋連結（R3）。
- 無待使用者決定的業務問題。

## 擬採方案與取捨
- **網頁**：Python 字串模板產生純靜態 HTML，CSS 內嵌，延用範例的配色、卡片、深色模式。不用 Jinja 等套件，維持只用標準函式庫。render 每次從所有 digest 重建整個 site/，所以不需要記住上次產生了什麼。
- **兩層回饋**：Telegram 訊息按鈕是「今天整體」的評分（一則訊息只放一列按鈕，避免洗版）；單則評分放在網頁上，用 deep link 回到 bot。替代方案「每則項目各送一則 Telegram 訊息」會一天送 30 則，太吵；「網頁直接呼叫 API」需要自架伺服器，不符免費、無伺服器的原則。
- **回饋格式**：JSON Lines 只附加不修改，同一則多次評分都保留，之後分析時取最新一筆；方便放進私人 Git repo 看差異。
- **安全**：collect 只接受 TELEGRAM_CHAT_ID 的更新，因為 bot 是公開可找到的；deep link 參數先用正規表示式完整比對再使用。
- **重複推送防護**：data/push/<日期>.json 記錄 message_id 與時間；排程重跑時不會重複推送。
- **共用 .env 讀取**：新增 ai_daily/env.py，llm.load_key 改用它，行為不變（R5 of llm-digest 的測試持續覆蓋）。

## 架構與資料影響
```
ai_daily/env.py              # 讀環境變數或 .env
ai_daily/publish/
  __init__.py
  html.py                    # R1～R3 頁面產生
  telegram.py                # Bot API 呼叫、token 遮蔽
  push.py                    # R4 訊息組裝與推送紀錄
  collect.py                 # R6～R7 收回饋
publish.toml
data/push/<日期>.json
site/            (.gitignore)
feedback/        (.gitignore；feedback.jsonl、state.json)
tests/test_publish.py
```

### Check: D1 - Offline tests
所有測試 SHALL 以替身取代 Telegram 呼叫，不發出網路請求、不需要真實 token；tests/test_publish.py SHALL 登錄在 workflow.config.json。

## 驗證與回復
- 自動測試：頁面跳脫與連結過濾、首頁歷史、deep link 格式、訊息長度截斷、重複推送防護、憑證檢查與遮蔽、兩種回饋解析、陌生 chat 忽略、offset 推進。
- 手動實機：使用者建立新 bot 後，實際 push 一次、在手機按按鈕與點網頁連結，再執行 collect 確認寫入，記錄在 review.md。
- 回復：只新增檔案與子指令，llm.load_key 改用 env.py 但介面不變；刪除 ai_daily/publish、ai_daily/env.py 並還原 llm.load_key 即可。
