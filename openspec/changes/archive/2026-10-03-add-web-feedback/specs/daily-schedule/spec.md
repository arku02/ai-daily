## MODIFIED Requirements

### Requirement: R4 - Secrets handling
workflow SHALL 只從 GitHub Secrets 取得 GEMINI_API_KEY、TELEGRAM_BOT_TOKEN、TELEGRAM_CHAT_ID、PROFILE_TOML、FEEDBACK_REPO_TOKEN 與 FEEDBACK_READ_KEY（collect 讀取網頁評分），以環境變數傳給指令；profile.toml SHALL 在執行時由 PROFILE_TOML 寫出且不被提交。workflow 的權限 SHALL 限縮為所需最小範圍（contents: write、pages: write、id-token: write）。

#### Scenario: Profile not committed
- **WHEN** daily workflow 提交 data/
- **THEN** 提交內容不含 profile.toml、.env 或 feedback/

#### Scenario: Read key only in collect
- **WHEN** 檢查 workflow 使用的 Secrets
- **THEN** FEEDBACK_READ_KEY 只出現在 collect workflow 的 collect 步驟，daily workflow 不使用
