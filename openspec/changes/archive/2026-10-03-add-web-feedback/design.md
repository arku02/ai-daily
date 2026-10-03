# 技術設計

## 已知事實
- 現行回饋連結由 ai_daily/publish/html.py 的 deep_link、feedback_html 產生，是 `<a href="https://t.me/...">`；網頁是 render_all 每次重建所有日期的純靜態 HTML，部署到 GitHub Pages（publish-feedback R1～R3、daily-schedule R1）。
- collect（ai_daily/publish/collect.py）以 state.json 的 offset 拉 Telegram 更新，寫入 feedback.jsonl；collect workflow 每 6 小時執行，FEEDBACK_DIR 指向私人 repo ai-daily-feedback。
- add-publish-feedback 的設計曾排除「網頁直接呼叫 API」，理由是需要自架伺服器、不符免費原則。使用者 2026-10-03 改為接受免費的 Cloudflare Worker，並要求加上通行證。
- Cloudflare 免費方案：Workers 每天 10 萬次請求；D1 每天 500 萬次讀取、10 萬次寫入、5 GB 儲存；Workers Rate Limiting 綁定可設定 60 秒內次數上限，計數以各資料中心為單位、非全域精確。
- URL 的 # 片段不會送到伺服器，GitHub Pages 與 Worker 都收不到通行證所在的片段。
- 本機有 Node 24（.integration 流程需要），Node 內建 Request、Response、fetch，可以直接載入 Worker 模組測試。

## 假設與待決問題
- 假設使用者願意註冊 Cloudflare 帳號並在瀏覽器完成 wrangler login（使用者 2026-10-03 已選此方案）。
- 手機上從 Telegram 打開連結時，可能使用 Telegram 內建瀏覽器，儲存空間與手機的一般瀏覽器分開。通行證存在哪個瀏覽器，就只有那個瀏覽器能直接送出；其他瀏覽器會退回 Telegram deep link，不會遺失回饋。README 說明這點。
- 無待決業務問題。

## 擬採方案與取捨
- **端點**：Cloudflare Worker＋D1。D1 用自動遞增 id，collect 以 `after=<最後 id>` 拉取，和 Telegram 的 offset 一樣只往前推，不需要刪除資料。替代方案 KV 需要列舉＋刪除，免費方案每天只有 1000 次寫入／刪除，較不適合；Google Apps Script＋試算表不需新帳號，但沒有次數限制可用，且回應會經過轉址，fetch 不易判斷成功與否。
- **兩把金鑰**：WEB_KEY（通行證，只能寫）存在瀏覽器；READ_KEY（只能讀）存在 GitHub Secret。通行證外流時，別人只能送評分，讀不到資料。
- **檢查順序**：先做次數上限，避免有人用大量請求猜通行證；再驗通行證；最後才做需要對外請求的「項目存在」檢查，未通過驗證的請求不會讓 Worker 去抓網頁。
- **項目存在**：Worker 抓 SITE_URL/<date>.html，確認含 `data-ref="<ref>"`，並請 Cloudflare 快取 5 分鐘。不另外發布一份項目清單，網頁本身就是清單。
- **網頁程式**：維持 `<a href=deep link>`，只多 data 屬性與一段內嵌程式。程式有通行證才攔截點擊；沒有通行證、程式沒載入或瀏覽器擋了 localStorage 時，都退回原本的 Telegram 行為。選擇記在 localStorage（`aidaily-fb:<日期>:<ref>`），重新打開頁面時仍顯示已選。
- **通行證連結**：`index.html#k=<WEB_KEY>`；程式存起來後立刻用 history.replaceState 移除片段，避免出現在瀏覽紀錄或被分享。由 `pass-link` 指令用 Telegram 傳送，關閉連結預覽。
- **collect**：Telegram 與 Worker 各自處理，任一邊失敗不影響另一邊寫入；兩邊共用 state.json（offset、web_after），依序讀寫。
- **endpoint 為空**時維持現況，部署 Worker 前合併本變更不影響使用中的網站。

## 架構與資料影響
```
worker/
  wrangler.toml        # Worker 名稱、D1 綁定、次數上限、ALLOWED_ORIGIN、SITE_URL（不含機密）
  schema.sql           # feedback 資料表
  src/index.js         # R8
  test/harness.mjs     # 測試用：記憶體 D1、假的次數上限與網頁，從 stdin 讀情境
ai_daily/publish/html.py     # R3：data 屬性與送出程式
ai_daily/publish/collect.py  # R10：collect_web
ai_daily/cli.py              # R9 pass-link；collect 呼叫 collect_web
.github/workflows/collect.yml  # FEEDBACK_READ_KEY
publish.toml                 # feedback.endpoint
```
feedback.jsonl 的網頁回饋多一個欄位 `via: "web"`；state.json 多一個欄位 `web_after`。機密：Worker secret WEB_KEY、READ_KEY；本機 .env 的 FEEDBACK_WEB_KEY、FEEDBACK_READ_KEY；GitHub Secret FEEDBACK_READ_KEY。

### Check: D1 - Config and registration
wrangler.toml SHALL 含 D1 綁定 DB、次數上限綁定 LIMITER（60 秒 20 次）、ALLOWED_ORIGIN 為 https://arku02.github.io，且不含 WEB_KEY、READ_KEY 的值；collect workflow 的 collect 步驟 SHALL 以 secrets.FEEDBACK_READ_KEY 提供 FEEDBACK_READ_KEY；Worker 測試 SHALL 以 Node 實際載入 worker/src/index.js 執行，不連網。

## 驗證與回復
- 自動測試（tests/test_publish.py 與新的 tests/test_worker.py）：網頁標記與 endpoint 過濾、通行證連結與遮蔽、collect 合併與錯誤處理、Worker 各狀態碼與讀取分頁、設定檔檢查。Worker 測試以 Node 執行真實模組，D1、次數上限與網頁抓取用假的替代。
- 手動實機：部署 Worker 後，在內建瀏覽器打開通行證連結、按評分、確認沒跳轉且 D1 有資料；不帶通行證的 curl 回 401；執行 collect workflow 確認寫入私人 repo。結果記在 review.md。
- 回復：把 publish.toml 的 feedback.endpoint 清空並重新部署網頁，就回到 Telegram deep link；Worker 可用 `wrangler delete` 移除。通行證外流時，產生新值、更新 Worker secret 與 .env，再執行 pass-link。
