## Purpose
每天從 Hacker News、Hugging Face、GitHub 與設定的 RSS 來源抓取 AI Agent 相關的候選項目，轉成統一格式、跨來源去重，並用每日快照計算星數與讚數的成長量，作為早報後續篩選與摘要的原始資料。

## ADDED Requirements

### Requirement: R1 - Unified item format
每個來源 SHALL 把抓到的資料轉成統一的項目格式，欄位為 source、id、title、url、summary、published_at、metrics 與 extra。id SHALL 在同一來源內唯一且跨日穩定：HN 為 story ID、HF 模型為模型 ID、HF 論文為論文 ID、GitHub 為 owner/repo、RSS 為連結網址。published_at SHALL 為 UTC ISO 8601 字串，來源沒有提供時 SHALL 為 null。metrics SHALL 只放數字或 null。

#### Scenario: HN story becomes an item
- **WHEN** HN 回傳一則 objectID 為 49896604、points 為 608、num_comments 為 472 的 story
- **THEN** 產生 source 為 hn、id 為 49896604 的項目，metrics 包含 points 608 與 comments 472，extra 包含 HN 討論頁網址

#### Scenario: HN story without url
- **WHEN** HN story 沒有 url 欄位（例如 Ask HN）
- **THEN** 項目的 url 為該則 HN 討論頁網址

### Requirement: R2 - Source filters from config
系統 SHALL 從 `sources.toml` 讀取各來源的開關與參數。HN SHALL 對每個設定的關鍵字查詢最近 window_hours 小時內、points 不低於 min_points 的 story。GitHub Search SHALL 查詢最近 created_within_days 天內新建、符合設定查詢字串的 repo，依星數排序。HF 模型 SHALL 只保留 pipeline_tag 在設定清單內的模型。RSS SHALL 只保留發布時間在 window_hours 小時內的項目。設定為 enabled = false 的來源 SHALL 不發出任何請求。

#### Scenario: HN points threshold
- **WHEN** min_points 為 30，HN 回傳 points 分別為 608 與 12 的兩則 story
- **THEN** 只保留 608 分那則

#### Scenario: Disabled source
- **WHEN** rss 設為 enabled = false
- **THEN** 不對任何 RSS 網址發出請求，輸出中 rss 狀態為 disabled

#### Scenario: HF pipeline filter
- **WHEN** 設定清單為 text-generation 與 image-text-to-text，熱門模型含一個 text-to-image 模型
- **THEN** 該 text-to-image 模型不出現在輸出

### Requirement: R3 - Growth from snapshots
系統 SHALL 每次執行時把所有 GitHub 項目的總星數與 HF 模型的讚數寫入當天快照。項目的 metrics SHALL 包含 stars_delta（GitHub）或 likes_delta（HF 模型），值為目前數字減去「執行日期之前最近一份快照」中的數字；該快照沒有這個項目或沒有任何先前快照時 SHALL 為 null，SHALL 不為 0。GitHub Trending 頁面上的「stars today」SHALL 另存為 stars_today。

#### Scenario: Delta from previous snapshot
- **WHEN** 9/29 的快照記錄 owner/repo 為 1000 星，9/30 抓到 1300 星
- **THEN** 9/30 輸出中該 repo 的 stars_delta 為 300

#### Scenario: First time seen
- **WHEN** 先前快照中沒有這個 repo
- **THEN** stars_delta 為 null

#### Scenario: Same day rerun
- **WHEN** 9/30 已有快照，當天再執行一次
- **THEN** 成長量仍和 9/29（或更早最近一份）快照比較，9/30 快照被覆寫

### Requirement: R4 - Cross-source dedupe
系統 SHALL 以正規化網址合併不同來源的相同項目。正規化 SHALL 包含：http 改 https、移除 www.、移除 utm_ 開頭的查詢參數與網址片段、移除結尾斜線、主機名稱轉小寫。合併後 SHALL 保留最先出現的項目，並在 also_in 中記錄其他來源的 source、id 與 metrics。來源順序 SHALL 為 github_trending、github_search、hf_models、hf_papers、hn、rss。

#### Scenario: HN links a trending repo
- **WHEN** GitHub Trending 有 https://github.com/NVIDIA/OpenShell，HN 也有一則連到 http://www.github.com/NVIDIA/OpenShell/?utm_source=hn 的 story
- **THEN** 輸出只有一個 OpenShell 項目，source 為 github_trending，also_in 含該則 HN 的 id 與 points

### Requirement: R5 - Source failure isolation
任一來源發生網路錯誤、HTTP 錯誤或解析錯誤時，系統 SHALL 記錄該來源狀態為 error 與錯誤訊息，並繼續抓取其他來源。至少一個來源成功時退出碼 SHALL 為 0；所有啟用的來源都失敗時退出碼 SHALL 為 1。錯誤訊息與輸出 SHALL 不包含 GitHub token。

#### Scenario: One source down
- **WHEN** GitHub Trending 回傳 HTTP 503，其他來源正常
- **THEN** 輸出含其他來源的項目，github_trending 狀態為 error，退出碼為 0

#### Scenario: All sources down
- **WHEN** 所有啟用來源都無法連線
- **THEN** 仍寫出含各來源錯誤狀態的輸出檔，退出碼為 1

### Requirement: R6 - Daily raw output
`python -m ai_daily fetch` SHALL 把結果寫到 `data/raw/<日期>.json`，日期預設為執行當下的台北時間日期，可用 `--date YYYY-MM-DD` 指定。檔案 SHALL 包含 date、fetched_at（UTC）、sources（各來源的 status、count、error）與 items。同一天重跑 SHALL 覆寫該檔。執行結束 SHALL 在標準輸出印出各來源的狀態與項目數。

#### Scenario: Default date is Taipei
- **WHEN** 在 UTC 2026-09-30T20:00 執行且未指定日期
- **THEN** 輸出檔為 data/raw/2026-10-01.json

#### Scenario: Summary printed
- **WHEN** 抓取完成，hn 有 12 項、rss 失敗
- **THEN** 標準輸出列出 hn ok 12 與 rss error 及其原因
