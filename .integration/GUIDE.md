# 整合流程 0.2.0：專案操作入口

本專案採 OpenSpec 1.13.1，模板改編 BMAD 規劃與 Spec Kit 澄清／一致性檢查方法。工具在 .integration，產品程式、原 README、package.json 與 lockfile 保留原位置。

所有以下命令都在**專案根目錄**執行。先讀 .integration/PROJECT-RULES.md，讓協作的 AI 也讀取它。未自動安裝全域指令或修改 AI 設定。

## 安裝與環境檢查

```text
npm ci --prefix .integration --ignore-scripts --no-audit --no-fund
node .integration/scripts/doctor.mjs
node .integration/scripts/run-tests.mjs
```

流程需要 Node >=20.19。Python 專案另準備 Python 與應用依賴，workflow.config.json 的 pythonExecutable 可填 PATH 中的 python 或專案內 .venv/Scripts/python.exe（Windows）／.venv/bin/python（其他系統）。doctor 只檢查環境與檔案存在，不代表測試已通過。
Node 測試路徑為 test/ 或 tests/ 下的 *.test.js／*.test.mjs；Python unittest 為 test_*.py。測試方法／名稱需對應 R／D 編號。初次沒有測試檔時，先建立真實測試；不要以空檔案宣告驗收。

## 每次變更

```text
node .integration/scripts/workflow.mjs new add-feature
node .integration/scripts/workflow.mjs check add-feature
node .integration/scripts/workflow.mjs verify add-feature
node .integration/scripts/workflow.mjs archive add-feature
```

new 後依 openspec/schemas/integrated/templates 寫 proposal、specs、design、tasks、review。check 前做內容審查，實作完成再 verify／archive。tasks 是唯一任務清單，機器產生的 .workflow/evidence 與 receipts 是實際執行證據。
小修改 lite 與完整流程 full 使用同一套模板。規格與任務都有覆蓋關係，且真實測試通過，才能交付。

## 失敗與恢復

- 尚未實作、問題未決：回 proposal／specs／design 修訂，再審查 review。
- 基準改動：比對現行規格，執行 workflow.mjs rebase <name>，重新審查。
- 測試失敗或證據過期：修正後重新 verify；不得手改證據。
- 封存後正式規格失敗：檔案可能已同步且沒有成功回條；先檢查 archive 與現行 spec，再以後續變更修訂，不盲目重跑同名 archive。沒有自動交易回滾。
- 導入後尚未開始工作，可用樣板庫 onboard rollback 指令和 .workflow/imports/<id>/manifest.json 復原。已修改工具檔或開始變更時會拒絕自動復原，避免刪掉新工作。

這是本地檢查，原生 OpenSpec archive 可以繞過。團隊強制約束需在受保護 CI 另行配置。工具不保證需求正確、測試語意充分或外部服務可用。

## 公開與隱私

封存保護歷史事實與結果，允許有紀錄的隱私去識別化，詳見 [專案規則](PROJECT-RULES.md) 的「歷史證據與隱私」。新日誌先去識別化再計算雜湊，doctor 的命令列輸出與新封存回條也會處理路徑。本機原始日誌與 `.workflow/imports/` 的 manifest／備份不公開。導入 manifest 不應修改路徑或雜湊後繼續作為 rollback 輸入。

公開副本須註明處理範圍與雜湊驗證限制；活動變更受影響時重新 verify，封存副本不得手改通過欄位或雜湊來冒充原始證據。`.gitignore` 不會移除已追蹤檔案或舊提交中的資訊，公開前也須檢查準備推送的歷史。

Git 倉庫建立後，在專案根目錄執行以下一次性啟用與歷史檢查；每個 clone 都需要啟用：

```text
node .integration/scripts/privacy.mjs install
node .integration/scripts/privacy.mjs history
```

之後正常提交與推送會先在本機檢查；發現私人路徑或無法檢查時阻擋，並保留原檔。既有 hooks 不會被覆蓋。檢查可被繞過，網站直接上傳也不在保護範圍；這不是零洩漏保證。可執行設定、本機覆寫與圖片等非文字檔案的審查方式見 [路徑隱私保護](PRIVACY.md)。
