# llm-digest Specification

## Purpose
把 source-fetch 產生的每日原始候選，透過免費的 Gemini 模型篩選並改寫成繁體中文的結構化早報內容：四個章節的深度項目與快速瀏覽、今天只看三件事、今天試一個，每則附摘要、重點、你可以怎麼用與真實來源連結。

## Requirements

### Requirement: R1 - Candidate preparation
digest SHALL 讀取 data/raw/<日期>.json，依 digest.toml 的每來源上限取候選：hn 依 points、github_trending 依 stars_today、github_search 依 stars_delta（為 null 時依 stars）、hf_models 依 likes_delta（為 null 時依 likes）、hf_papers 依 upvotes、rss 依發布時間，皆由大到小。每個候選 SHALL 取得穩定的短代號（c1、c2…，依上述順序編號），送給 LLM 的精簡清單 SHALL 只含代號、來源、標題、截斷後的摘要與數字指標，SHALL 不含網址。原始檔不存在時 SHALL 以退出碼 2 結束並提示先執行 fetch。

#### Scenario: Per-source cap
- **WHEN** hn 上限為 20，原始資料有 29 則 HN 項目
- **THEN** 候選只含 points 最高的 20 則

#### Scenario: Missing raw file
- **WHEN** data/raw/2026-10-01.json 不存在時執行 digest --date 2026-10-01
- **THEN** 退出碼為 2，訊息提示先執行 fetch，沒有任何 API 呼叫

### Requirement: R2 - Selection
digest SHALL 以一次 LLM 呼叫，依 profile 的背景、興趣與排除主題，從候選中選出 news、models、arch、github 四個章節的深度項目與快速瀏覽項目、三句「今天只看三件事」，以及至多 3 個依優先順序排列的「今天試一個」候選。程式 SHALL 驗證回應：不存在的代號與未知章節 SHALL 被丟棄；同一代號只保留第一次出現；每章節深度與快速瀏覽數量 SHALL 截斷到 digest.toml 的上限；今天試一個候選中不存在或重複的代號 SHALL 被丟棄。選題提示 SHALL 包含 profile 的排除主題與今天試一個的挑選規則。

#### Scenario: Invalid selections dropped
- **WHEN** LLM 回傳的 news 含 c3、c999、c3，另有未知章節 gossip
- **THEN** news 只含 c3，gossip 被丟棄

#### Scenario: Section cap
- **WHEN** news 深度上限為 5，LLM 選了 7 個有效代號
- **THEN** news 深度只保留前 5 個

#### Scenario: Exclusions in prompt
- **WHEN** profile 的排除主題為融資新聞與公司人事
- **THEN** 選題提示含這兩個主題

### Requirement: R3 - Enrichment
對每個深度項目，digest SHALL 嘗試抓取補充內容：GitHub 項目抓 README、HF 模型抓模型卡、HN 與 RSS 抓原文網頁的純文字；HF 論文使用既有摘要。補充內容 SHALL 截斷到 digest.toml 設定的字數（max_chars；今天試一個候選使用較大的 try_one_max_chars，以取得完整安裝步驟）。任何補充抓取失敗 SHALL 不中斷流程，該項目改用原始摘要。

#### Scenario: Enrichment failure
- **WHEN** 某則新聞的原文網址回應 403
- **THEN** 該項目仍進入寫作，使用原始摘要

### Requirement: R4 - Writing with real sources
digest SHALL 依章節分批呼叫 LLM，為每個深度項目產生繁體中文的 title、tags、summary、key_points（1～4 點）、how_to_use；快速瀏覽項目產生 title 與一句話說明；今天試一個產生 why、至多 3 個 steps 與 success_check。每個項目的 sources SHALL 由程式從原始資料產生（主要網址、HN 討論頁、also_in 中的 HN 討論頁、論文的 arXiv 與 GitHub 連結），SHALL 不採用 LLM 回傳的任何網址。某批回應格式不合時 SHALL 重試一次；仍不合格的項目 SHALL 以原始標題與原始摘要產生並標記 fallback 為 true，其他項目不受影響。寫作今天試一個時 SHALL 依候選順序逐一嘗試；模型回傳 null 或 skip 為 true 表示該候選不符合挑選規則，SHALL 記錄原因並改試下一個；所有候選都被跳過時 try_one SHALL 為 null，SHALL 不降級。

#### Scenario: Sources come from raw data
- **WHEN** LLM 回應中夾帶 https://fake.example.com
- **THEN** 輸出不含該網址，項目 sources 為原始資料中的網址

#### Scenario: Fallback item
- **WHEN** 某批兩次回應都缺少 c7 的 summary
- **THEN** c7 以原始標題與摘要輸出、fallback 為 true，同批其他合格項目正常輸出

#### Scenario: Try one skipped by writer
- **WHEN** 今天試一個有 c5、c9 兩個候選，模型對 c5 回傳 {"skip": true}，對 c9 回傳完整內容
- **THEN** try_one 為 c9，warnings 記錄 c5 被跳過；若兩個都被跳過則 try_one 為 null

### Requirement: R5 - Gemini client and key handling
LLM 客戶端 SHALL 從環境變數 GEMINI_API_KEY 讀取 key，沒有時讀取專案根目錄的 .env。沒有 key 時 digest SHALL 在任何 API 呼叫前以退出碼 2 結束，並提示在 .env 設定。請求 SHALL 要求 JSON 回應。遇到 429、5xx 或 404 時 SHALL 依 digest.toml 的模型清單改用下一個模型；清單全部失敗時 digest SHALL 以退出碼 1 結束。key SHALL 不出現在任何輸出、錯誤訊息或檔案中。

#### Scenario: Missing key
- **WHEN** 環境變數與 .env 都沒有 GEMINI_API_KEY
- **THEN** 退出碼為 2，提示設定 .env，沒有 API 呼叫

#### Scenario: Quota fallback
- **WHEN** 第一個模型回應 429，第二個模型正常
- **THEN** 該次呼叫使用第二個模型完成，輸出的 models_used 含第二個模型

#### Scenario: Key masked
- **WHEN** API 錯誤訊息包含 key
- **THEN** 顯示的錯誤中 key 被替換成 ***

### Requirement: R6 - Digest output and CLI
`python -m ai_daily digest` SHALL 預設處理台北時間今天，可用 --date 指定，輸出 data/digest/<日期>.json，內容含 date、generated_at、models_used、llm_calls、tldr、sections（news、models、arch、github，各含 items 與 brief）與 try_one。`--dry-run` SHALL 只印出各來源候選數與選題提示的字元數，SHALL 不需要 key，也不呼叫 API、不寫檔。

#### Scenario: Dry run
- **WHEN** 沒有設定 key 時執行 digest --dry-run
- **THEN** 印出候選數與提示長度，退出碼 0，沒有 API 呼叫與輸出檔

#### Scenario: Output shape
- **WHEN** digest 成功完成
- **THEN** data/digest/<日期>.json 含上述欄位，llm_calls 等於實際 API 呼叫次數

### Requirement: R7 - Private profile
digest SHALL 讀取 profile.toml 作為使用者背景；不存在時 SHALL 改讀 profile.example.toml 並在輸出中提示。profile.toml SHALL 被 .gitignore 排除。

#### Scenario: Example fallback
- **WHEN** 專案沒有 profile.toml
- **THEN** 使用 profile.example.toml，標準輸出提示可以建立 profile.toml
