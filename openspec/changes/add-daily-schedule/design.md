# 技術設計

## 已知事實
- 2026-09-30：arku02/ai-daily 對匿名 API 回應 200（公開）、arku02/ai-daily-feedback 回應 404（私人）；以使用者本機 Git Credential Manager 執行 git ls-remote，兩者皆可存取且沒有任何 ref（空 repo）。
- 本機沒有安裝 gh CLI。
- 第 1～3 步的指令（fetch、digest、render、push、collect）都已實作並實機驗證；push 以 data/push/<日期>.json 防重複；collect 以 FEEDBACK_DIR 決定回饋資料夾。
- 本機實測：fetch 約 13 秒、digest 約 80 秒。
- 專案只用 Python 標準函式庫，Actions 不需要 pip install。

## 假設與待決問題
- GitHub 排程在尖峰時會延遲（官方文件說明高負載時可能延後或丟棄），所以 08:45 開始；實際推送時間需觀察幾天。
- actions/checkout 無法取出沒有任何提交的 repo，所以 ai-daily-feedback 需要先推一個初始提交（README）。
- Pages 的來源需要使用者在 repo 設定頁改成「GitHub Actions」。
- 無待使用者決定的業務問題；推送到兩個遠端 repo 與設定 Secrets 需使用者同意與操作。

## 擬採方案與取捨
- **daily 分三個工作**：build（fetch → digest → render → 提交 data → 上傳 Pages 成品）、deploy（actions/deploy-pages）、notify（checkout 最新 main → push → 提交推送紀錄）。deploy 必須是獨立工作並綁定 github-pages environment，notify 依賴 deploy，所以推送時網頁已上線。
- **digest 失敗仍保留原始資料**：提交 data 的步驟使用 `if: always() && steps.fetch.outcome == 'success'`；render 與上傳只在 digest 成功後執行，build 以失敗結束讓 deploy、notify 不執行。
- **collect 獨立 workflow**：每 6 小時，只 checkout 私人 repo 到 feedback-repo/，不改動 ai-daily 的內容。Telegram 保留未確認更新約 24 小時，6 小時一次足夠。
- **concurrency 群組 ai-daily、cancel-in-progress: false**：兩個 workflow 排隊執行。
- **FEEDBACK_REPO_TOKEN 用 fine-grained token**，只授權 ai-daily-feedback 的 Contents 讀寫；即使外洩也碰不到其他 repo。GITHUB_TOKEN 無法寫其他 repo，所以這個 token 是必要的。
- **失敗通知用 curl 呼叫 sendMessage**：token 以 secret 傳入，Actions 會在日誌中遮蔽。
- **Python 3.13**：與本機相同。

## 架構與資料影響
```
.github/workflows/daily.yml     # build → deploy → notify
.github/workflows/collect.yml   # 每 6 小時收回饋 → ai-daily-feedback
tests/test_schedule.py          # 以文字解析檢查 workflow 的關鍵設定
```
ai-daily 的 data/ 由 github-actions[bot] 每日提交；ai-daily-feedback 只有 README、feedback.jsonl、state.json。

### Check: D1 - Workflow static checks
tests/test_schedule.py SHALL 在不連網、不依賴 YAML 套件的情況下檢查兩個 workflow 的 cron、指令順序、needs 關係、concurrency、權限與使用的 secret 名稱，並登錄在 workflow.config.json。

## 驗證與回復
- 自動測試只能檢查設定文字，無法證明 GitHub 上會成功；實際以 workflow_dispatch 手動觸發一次 daily 與 collect 驗證，結果記錄在 review.md。
- 回復：在 GitHub 停用 workflow，或刪除 .github/workflows；Secrets 可在 repo 設定頁刪除；fine-grained token 可在個人設定撤銷。
