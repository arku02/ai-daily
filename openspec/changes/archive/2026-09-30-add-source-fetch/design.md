# 技術設計

## 已知事實
- 專案目前沒有產品程式，這是第一個變更。
- 2026-09-30 手動整理範例時實際呼叫過以下端點，回應格式如下：
  - HN Algolia：`https://hn.algolia.com/api/v1/search?query=<kw>&tags=story&numericFilters=created_at_i><ts>,points><n>`，`hits[]` 含 objectID、title、url（可能缺）、points、num_comments、created_at_i。
  - HF 模型：`https://huggingface.co/api/models?sort=trendingScore&limit=N`，陣列元素含 id、likes、downloads、pipeline_tag、trendingScore、createdAt。
  - HF Daily Papers：`https://huggingface.co/api/daily_papers?date=YYYY-MM-DD`，元素的 `paper` 含 id、title、summary、upvotes、githubRepo、publishedAt，外層含 organization。
  - GitHub Trending：`https://github.com/trending?since=daily` 是 HTML，每個 repo 是一個 `<article class="Box-row">`，其中有 `href="/owner/repo"`、`<p class="col-9 ...">` 描述、`itemprop="programmingLanguage"`、`/owner/repo/stargazers` 連結內的總星數，以及「N stars today」。
  - GitHub Search：`https://api.github.com/search/repositories?q=<q>+created:>YYYY-MM-DD&sort=stars&order=desc`，未登入時每分鐘限 10 次。
- 範例中用 WebFetch 抓 openai.com、cnbc.com 會回應 403，所以新聞類只採用有 RSS 的來源，並把 HN 當作新聞熱度的主要訊號。
- Python 3.13.7 已安裝；專案 .venv 已建立。

## 假設與待決問題
- 假設 GitHub Actions 的 runner 可以正常存取以上端點（第 4 步實際驗證）。
- 假設 HF Daily Papers 用執行日期前一天查詢比較完整（台北早上 9 點時，美國當天還沒結束）。可在設定中調整。
- RSS 預設來源只放已知有提供 feed 的站點；若某個 feed 失效，R5 會把它記成 error，不影響其他來源。
- 沒有待使用者決定的業務問題。

## 擬採方案與取捨
- **只用標準函式庫**：urllib 抓取、json、xml.etree 解析 RSS/Atom、re 解析 Trending HTML、tomllib 讀設定；台北時間用固定 UTC+8（台灣無日光節約，且 Windows 的 Python 沒有內建 tzdata，zoneinfo 會失敗）。避免在 Actions 上多裝套件，也減少供應鏈風險。取捨：Trending 用正規表示式解析比較脆弱，但頁面結構簡單，失敗時有 R5 保護。
- **HTTP 層集中在一個函式**（`http.get_text`），測試時用替身取代，所有來源測試都不連網。帶 User-Agent、逾時 20 秒、失敗重試 1 次；若有環境變數 GITHUB_TOKEN，只在 api.github.com 的請求加上 Authorization。
- **每個來源一個模組**，各自提供 `fetch(cfg, ctx) -> list[Item]`，由 `pipeline.run` 依序呼叫並包上錯誤處理。
- **去重**：依 R4 的來源順序合併，GitHub 來源優先，這樣 repo 會保留星數資料，HN 的熱度則記在 also_in。
- **快照**：`data/snapshots/<日期>.json` 格式為 `{"github": {"owner/repo": stars}, "hf_models": {"id": likes}}`。比較對象是檔名日期小於執行日期的最新一份，所以同一天重跑結果一致。
- **資料放在 repo 裡**：原始資料都是公開資訊，存 JSON 就不需要資料庫，也方便在 GitHub 上直接查看歷史。

替代方案：用 feedparser、requests、BeautifulSoup 可以少寫一些解析程式，但要多管理依賴，而且目前的資料量不需要。

## 架構與資料影響
```
ai_daily/
  __main__.py      # python -m ai_daily
  cli.py           # fetch 子指令、--date、--config、--out
  config.py        # 讀 sources.toml
  http.py          # get_text / get_json，token 遮蔽
  model.py         # Item dataclass、網址正規化
  snapshot.py      # 讀寫快照、計算成長量
  pipeline.py      # 呼叫各來源、失敗隔離、去重、輸出
  sources/ hn.py hf.py github.py rss.py
sources.toml
data/raw/<date>.json
data/snapshots/<date>.json
tests/test_fetch.py + tests/fixtures/
```

### Check: D1 - Offline tests
所有測試 SHALL 以替身取代 HTTP 層並使用 tests/fixtures 的回應樣本，執行時不發出任何網路請求；新測試檔 SHALL 登錄在 workflow.config.json 的 testFiles。

## 驗證與回復
- 測試：unittest，fixture 取自 2026-09-30 實際回應並縮減筆數；另外手動實際執行一次 fetch，確認對真實端點可用（記錄在 review.md，不當作自動測試）。
- 風險：Trending HTML 改版、API 限流。兩者都由 R5 隔離，並在輸出中留下錯誤原因。
- 回復：這個變更只新增檔案，刪除 ai_daily/、sources.toml、data/ 即可回復。
