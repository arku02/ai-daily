"""R4：分章節寫作。連結一律由程式從原始資料產生，不採用 LLM 回傳的網址。"""

from ..model import normalize_url
from ..sources.hn import discussion_url
from .llm import BadResponse
from .select import SECTIONS, profile_text

SOURCE_LABELS = {
    "github_trending": "GitHub",
    "github_search": "GitHub",
    "hf_models": "Hugging Face",
    "hf_papers": "HF Papers",
    "hn": "原文",
}

STYLE = """寫作要求：
- 繁體中文、台灣用語（例如「程式」「資料」「預設」），語氣像懂技術的同事在分享，不要浮誇。
- 只能根據下面提供的資料寫；資料沒有的數字、日期、功能不要自己補。廠商自己的說法要標明是官方宣稱。
- 「你可以怎麼用」要具體連結到讀者的技術與工作，例如在 LangGraph 的哪個環節、解決資料分析或自動化的什麼問題；真的沒關係就直說「跟你的工作關係不大」並說明為什麼仍值得知道。
- 不要輸出任何網址。"""


def sources_for(item):
    out = []

    def add(label, url):
        if url and normalize_url(url) not in {normalize_url(s["url"]) for s in out}:
            out.append({"label": label, "url": url})

    source = item["source"]
    extra = item.get("extra", {})
    if source == "hn":
        if item["url"] != extra.get("discussion"):
            add("原文", item["url"])
        add(f"HN 討論（{item['metrics'].get('points')} 分）", extra.get("discussion"))
    elif source == "rss":
        add(extra.get("feed") or "原文", item["url"])
    else:
        add(SOURCE_LABELS.get(source, "來源"), item["url"])
    if source == "hf_papers":
        add("arXiv", extra.get("arxiv"))
        add("GitHub", extra.get("github"))
    for other in item.get("also_in", []):
        if other["source"] == "hn":
            add(f"HN 討論（{other['metrics'].get('points')} 分）", discussion_url(other["id"]))
    return out


def _str(v):
    return isinstance(v, str) and v.strip() != ""


def _str_list(v, lo, hi):
    if not isinstance(v, list):
        return None
    items = [s.strip() for s in v if _str(s)]
    return items[:hi] if len(items) >= lo else None


def valid_item(r):
    if not isinstance(r, dict) or not all(_str(r.get(k)) for k in ("title", "summary", "how_to_use")):
        return None
    points = _str_list(r.get("key_points"), 1, 4)
    if points is None:
        return None
    tags = _str_list(r.get("tags") or [], 0, 4) or []
    return {"title": r["title"].strip(), "tags": tags, "summary": r["summary"].strip(),
            "key_points": points, "how_to_use": r["how_to_use"].strip()}


def valid_brief(r):
    if not isinstance(r, dict) or not (_str(r.get("title")) and _str(r.get("one_liner"))):
        return None
    return {"title": r["title"].strip(), "one_liner": r["one_liner"].strip()}


def valid_try(r):
    if not isinstance(r, dict) or not all(_str(r.get(k)) for k in ("title", "why", "success_check")):
        return None
    steps = _str_list(r.get("steps"), 1, 3)
    if steps is None:
        return None
    return {"title": r["title"].strip(), "why": r["why"].strip(), "steps": steps,
            "success_check": r["success_check"].strip()}


def _base(c):
    it = c.item
    return {"ref": c.ref, "source": it["source"], "id": it["id"], "metrics": it["metrics"],
            "sources": sources_for(it)}


def fallback_item(c):
    it = c.item
    return {**_base(c), "title": it["title"], "tags": [], "summary": (it.get("summary") or "")[:400],
            "key_points": [], "how_to_use": "", "fallback": True}


def fallback_brief(c):
    it = c.item
    return {**_base(c), "title": it["title"], "one_liner": (it.get("summary") or "")[:120], "fallback": True}


def fallback_try(c):
    it = c.item
    return {**_base(c), "title": it["title"], "why": (it.get("summary") or "")[:200], "steps": [],
            "success_check": "", "fallback": True}


def _material(c, text):
    it = c.item
    metrics = ", ".join(f"{k}={v}" for k, v in it["metrics"].items() if v is not None)
    return f"### {c.ref}｜{it['source']}｜{it['title']}\n指標：{metrics or '無'}\n資料：\n{text}\n"


def section_prompt(name, deep, brief, texts, profile, date):
    deep_part = "\n".join(_material(c, texts.get(c.ref, c.item.get("summary", ""))) for c in deep) or "（無）"
    brief_part = "\n".join(_material(c, (c.item.get("summary") or "")[:500]) for c in brief) or "（無）"
    return f"""你在替下面這位讀者寫 {date} 的 AI Agent 早報，章節是「{SECTIONS[name]}」。

## 讀者
{profile_text(profile)}

{STYLE}

## 深度項目（每則都要寫）
{deep_part}

## 快速瀏覽項目（每則一句話）
{brief_part}

## 輸出
只輸出 JSON：
{{"items": [{{"ref": "c1", "title": "中文標題，40 字內", "tags": ["2～4 個短標籤"],
   "summary": "摘要，120～250 字", "key_points": ["重點 1～4 點"], "how_to_use": "你可以怎麼用，80～200 字"}}],
 "brief": [{{"ref": "c2", "title": "中文標題", "one_liner": "一句話，50 字內"}}]}}
"""


def try_prompt(c, text, profile, date):
    return f"""你在替下面這位讀者寫 {date} 早報的「今天試一個」：讓讀者今天花 15～30 分鐘實際動手試。

## 讀者
{profile_text(profile)}

{STYLE}
- steps 最多 3 步，每步一個具體動作；只有資料中出現的安裝指令才可以寫進去。
- success_check 寫「怎樣算成功」，要能實際檢查。

## 項目
{_material(c, text)}

## 輸出
只輸出 JSON：{{"title": "動詞開頭的標題", "why": "為什麼挑它，60 字內", "steps": ["..."], "success_check": "..."}}
如果這個項目不符合「今天試一個」規則（例如一定要讀者沒有的付費 key），只輸出 {{"skip": true, "reason": "原因"}}。
"""


def _by_ref(resp, key):
    out = {}
    if isinstance(resp, dict) and isinstance(resp.get(key), list):
        for r in resp[key]:
            if isinstance(r, dict) and isinstance(r.get("ref"), str):
                out.setdefault(r["ref"], r)
    return out


def write_section(llm, name, deep, brief, texts, profile, date, warnings):
    """回傳 (items, briefs)。整批重試一次，之後逐項降級。"""
    if not deep and not brief:
        return [], []
    prompt = section_prompt(name, deep, brief, texts, profile, date)
    good_items, good_briefs = {}, {}
    for _ in range(2):
        try:
            resp = llm.generate_json(prompt)
        except BadResponse as e:
            warnings.append(f"{name}: {e}")
            continue
        for ref, r in _by_ref(resp, "items").items():
            v = valid_item(r)
            if v and ref not in good_items:
                good_items[ref] = v
        for ref, r in _by_ref(resp, "brief").items():
            v = valid_brief(r)
            if v and ref not in good_briefs:
                good_briefs[ref] = v
        if all(c.ref in good_items for c in deep) and all(c.ref in good_briefs for c in brief):
            break
    items = [{**_base(c), **good_items[c.ref], "fallback": False} if c.ref in good_items else fallback_item(c)
             for c in deep]
    briefs = [{**_base(c), **good_briefs[c.ref], "url": c.item["url"], "fallback": False}
              if c.ref in good_briefs else {**fallback_brief(c), "url": c.item["url"]}
              for c in brief]
    for x in items + briefs:
        if x["fallback"]:
            warnings.append(f"{name}: {x['ref']} 使用原始資料（fallback）")
    return items, briefs


def write_try_one(llm, c, text, profile, date, warnings):
    prompt = try_prompt(c, text, profile, date)
    for _ in range(2):
        try:
            resp = llm.generate_json(prompt)
        except BadResponse as e:
            warnings.append(f"try_one: {e}")
            continue
        if resp is None or (isinstance(resp, dict) and resp.get("skip") is True):
            reason = resp.get("reason", "") if isinstance(resp, dict) else ""
            warnings.append(f"try_one: 模型判斷 {c.ref}（{c.item['id']}）不符合規則，跳過：{reason}")
            return None
        v = valid_try(resp)
        if v:
            return {**_base(c), **v, "fallback": False}
    warnings.append(f"try_one: {c.ref} 使用原始資料（fallback）")
    return fallback_try(c)
