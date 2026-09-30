"""R2：選題提示與回應驗證。"""

SECTIONS = {
    "news": "AI Agent 新聞：產品發布、事件、產業動態",
    "models": "新 AI 模型：商用或開源模型發布、新類型的模型",
    "arch": "新架構與論文：正在流行的設計模式、值得注意的論文",
    "github": "GitHub 爆紅專案：成長最快、對讀者有用的 repo",
}


def profile_text(profile):
    def lst(key):
        return "、".join(profile.get(key, [])) or "（未設定）"
    rules = "\n".join(f"  - {r}" for r in profile.get("try_one_rules", []))
    return (
        f"- 背景：{profile.get('background', '')}\n"
        f"- 技術：{lst('stack')}\n"
        f"- 工作：{lst('work')}\n"
        f"- 興趣：{lst('interests')}\n"
        f"- 不想看：{lst('exclude_topics')}\n"
        f"- 「今天試一個」規則：\n{rules}"
    )


def build_prompt(lines, profile, caps, date, empty_sections=()):
    sec = "\n".join(
        f"- {name}：{desc}（深度最多 {caps[name]['items']} 則、快速瀏覽最多 {caps[name]['brief']} 則）"
        for name, desc in SECTIONS.items()
    )
    retry_note = ""
    if empty_sections:
        names = "、".join(f"{n}（{SECTIONS[n].split('：')[0]}）" for n in empty_sections)
        retry_note = f"## 注意\n上一次選題這些章節是空的：{names}。這次請務必替它們選出深度項目。\n\n"
    return f"""你是 AI Agent 領域的資深編輯，要替一位讀者編 {date} 的早報，完整版閱讀時間約 20 分鐘。

## 讀者
{profile_text(profile)}

## 章節
{sec}

## 選題規則
1. 只能從下方候選清單選，用代號（例如 c12）表示，不要自己編代號。
2. 同一件事只選一個代號，一個代號只能出現一次。「同一件事」包含：同一個產品或模型發表的官方文章、媒體報導、HN 討論與 GitHub repo；同一場發表會的多個公告若重點相同也算。選資訊最完整的那個（通常是官方文章或 repo），其他來源不要再選。
3. 完全排除「不想看」的主題。
4. 優先選：對讀者工作有直接用處、熱度高（points、stars_today、upvotes 高）、屬於讀者興趣的項目。
5. 深度項目放最重要的；次要但值得知道的放快速瀏覽。每個章節深度至少選 2 則（該類候選真的不足才例外）；新模型可從 hf_models、官方發布新聞挑，新架構與論文可從 hf_papers 挑。
6. tldr：寫 3 句繁體中文（台灣用語），總結今天最重要的三件事，每句 60 字以內。
7. try_one：依「今天試一個」規則挑最多 3 個代號，最適合的放前面；注意讀者可用的 API，需要讀者沒有的付費 key 的不要選。沒有合適的就填 []。

## 候選清單（代號 | 來源 | 標題 | 類別 | 指標 | 摘要）
{chr(10).join(lines)}

{retry_note}## 輸出
只輸出 JSON，格式：
{{"tldr": ["...", "...", "..."],
 "sections": {{"news": {{"items": ["c1"], "brief": ["c2"]}}, "models": {{"items": [], "brief": []}},
              "arch": {{"items": [], "brief": []}}, "github": {{"items": [], "brief": []}}}},
 "try_one": ["c3", "c7"]}}
"""


def empty_sections(selection):
    return [n for n in SECTIONS if not selection["sections"][n]["items"]]


def completeness(selection):
    """越小越完整：先比空章節數，再比深度總數。"""
    return (len(empty_sections(selection)), -sum(len(s["items"]) for s in selection["sections"].values()))


def validate(resp, valid_refs, caps):
    if not isinstance(resp, dict):
        resp = {}
    seen = set()
    sections = {}
    raw_sections = resp.get("sections") if isinstance(resp.get("sections"), dict) else {}
    for name in SECTIONS:
        entry = raw_sections.get(name) if isinstance(raw_sections.get(name), dict) else {}
        sections[name] = {}
        for kind in ("items", "brief"):
            refs = []
            for ref in entry.get(kind) or []:
                if isinstance(ref, str) and ref in valid_refs and ref not in seen:
                    seen.add(ref)
                    refs.append(ref)
            sections[name][kind] = refs[: int(caps[name][kind])]
    tldr = [t.strip() for t in resp.get("tldr") or [] if isinstance(t, str) and t.strip()][:3]
    raw_try = resp.get("try_one")
    if isinstance(raw_try, str):
        raw_try = [raw_try]
    try_one = []
    for ref in raw_try if isinstance(raw_try, list) else []:
        if isinstance(ref, str) and ref in valid_refs and ref not in try_one:
            try_one.append(ref)
    return {"tldr": tldr, "sections": sections, "try_one": try_one[:3]}
