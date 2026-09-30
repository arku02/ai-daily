# 審查紀錄

## 結構化審查
```json
{
  "mode": "full",
  "decision": "ready",
  "reviewer": "Claude Opus 5.5：提案、規格、設計與任務交叉審查",
  "rationale": "範圍對應使用者 2026-09-30 確認的第 3 步（網頁、Telegram、回饋按鈕、回饋另存私人位置），排程、部署、私人 repo 推送列為第 4 步。R1 規定跳脫與只輸出 http(s) 連結；R3、R4 的 deep link 與 callback data 都在 Telegram 的 64 字元限制內（fb-YYYYMMDD-cNNN-v 約 20 字元）；R4 以推送紀錄防止排程重跑重複推送，並保證截斷後仍含網址；R5 缺憑證在請求前失敗且遮蔽 token；R6 只接受使用者 chat id，格式不符也推進 offset 以免卡住；R7 讓回饋資料夾可由第 4 步指到私人 repo。不共用 arxiv-digest 的 bot 的理由有程式證據。每項需求與 D1 都有任務與測試對應。無待決業務問題。",
  "openQuestions": [],
  "coverage": [
    { "requirement": "R1", "task": "1.1", "test": "tests/test_publish.py" },
    { "requirement": "R2", "task": "1.2", "test": "tests/test_publish.py" },
    { "requirement": "R3", "task": "1.3", "test": "tests/test_publish.py" },
    { "requirement": "R4", "task": "1.4", "test": "tests/test_publish.py" },
    { "requirement": "R5", "task": "1.5", "test": "tests/test_publish.py" },
    { "requirement": "R6", "task": "1.6", "test": "tests/test_publish.py" },
    { "requirement": "R7", "task": "1.7", "test": "tests/test_publish.py" },
    { "requirement": "D1", "task": "1.8", "test": "tests/test_publish.py" }
  ]
}
```

## 檢查內容
- 需求來源：使用者 2026-09-30 的決定（Telegram + 網頁、20 分鐘深度版、要回饋按鈕、回饋另存私人 repo、repo 名稱 ai-daily／ai-daily-feedback）。
- 設計區分已知事實（Telegram 限制、arxiv-digest 的 offset 行為）、假設（Pages 網址、deep link 在既有對話的行為）與方案。
- 不需要 ADR；兩層回饋的取捨記在 design.md。
- 手動實機確認（非自動測試）：2026-09-30 使用者建立新 bot @arku_ai_daily_bot，按 Start 後執行 push，手機與電腦都收到 1027 字元的訊息與三個按鈕。使用者在手機按「👍 有用」、在電腦點 deep link（fb-20260930-c12-1），collect 寫入 2 筆（day 1 筆、item 1 筆）；該 deep link 是手動構造的測試連結，c12 不在當天 digest，所以正確標記 unknown_item。
- 實機觀察：手機當時顯示 Connecting…，按鈕更新延後才送達；第一次 collect 在更新到達前執行，所以收到 0 筆，更新未遺失，第二次 collect 收到。按鈕按下後的「已記錄」回覆要等 collect 執行才出現，第 4 步排程後最多延遲數小時；Telegram 對過久的 callback 不接受回覆，_reply 會略過錯誤、不影響記錄。Telegram 介面只顯示 /start，參數仍會送達 bot。
- 網頁「完整版」連結要等第 4 步部署 Pages 後才會生效。

## 實際驗證
尚未執行。執行 verify 後讀取 .workflow/evidence/add-publish-feedback.json 與對應測試輸出。
