"""R1～R3：從 data/digest/*.json 產生 site/ 靜態網頁。"""

import json
from datetime import date as Date
from html import escape
from pathlib import Path

WEEKDAYS = "一二三四五六日"
SECTIONS = [
    ("news", "📰", "AI Agent 新聞"),
    ("models", "🧠", "新 AI 模型"),
    ("arch", "🏗️", "新架構與論文"),
    ("github", "⭐", "GitHub 爆紅專案"),
]
FEEDBACK = [(0, "👎 沒興趣"), (1, "👍 有用"), (2, "⭐ 超有用")]

CSS = """
:root{--bg:#f7f6f3;--card:#fff;--ink:#1d1d1f;--muted:#6b6b70;--line:#e4e2dc;--accent:#2f6fde;
--accent-soft:#e8f0fd;--use:#0f7b5f;--use-soft:#e6f5ef;--warn:#b25e09;--warn-soft:#fdf1e3;--tag:#f0eee9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--card:#1d1d20;--ink:#ececee;
--muted:#9a9aa1;--line:#2e2e33;--accent:#7aa7ff;--accent-soft:#1f2a40;--use:#4fd1a5;--use-soft:#15302a;
--warn:#f0a95a;--warn-soft:#352715;--tag:#2a2a2f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.75 "Noto Sans TC","PingFang TC","Microsoft JhengHei",system-ui,sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:24px 16px 80px}
header{padding:8px 0 20px;border-bottom:1px solid var(--line);margin-bottom:24px}
.kicker{font-size:13px;color:var(--muted);letter-spacing:.05em}
.kicker a{color:var(--muted)}
h1{font-size:30px;line-height:1.3;margin:6px 0 4px}
.meta{color:var(--muted);font-size:14px}
.tldr{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin:20px 0}
.tldr h2{font-size:15px;margin:0 0 8px;color:var(--muted);font-weight:600}
.tldr ol{margin:0;padding-left:22px}.tldr li{margin:4px 0}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 28px}
nav a{background:var(--tag);color:var(--ink);text-decoration:none;font-size:14px;padding:5px 12px;border-radius:99px}
nav a:hover{background:var(--accent-soft);color:var(--accent)}
section{margin:40px 0 0}section>h2{font-size:22px;margin:0 0 12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:14px 0}
.card h3{font-size:18px;line-height:1.45;margin:0 0 6px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px}
.tag{font-size:12px;background:var(--tag);color:var(--muted);padding:1px 8px;border-radius:6px}
.tag.hot{background:var(--warn-soft);color:var(--warn)}
.card p{margin:6px 0}
.label{font-weight:700;font-size:14px;margin:12px 0 2px;color:var(--muted)}
.card ul,.card ol{margin:4px 0;padding-left:20px}.card li{margin:3px 0}
.use{background:var(--use-soft);border-radius:10px;padding:10px 14px;margin:12px 0 6px}
.use .label{color:var(--use);margin-top:0}
.src{font-size:13px;color:var(--muted);margin-top:10px;word-break:break-word}
.src a,.brief a,.list a{color:var(--accent)}
.fb{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.fb a{font-size:13px;border:1px solid var(--line);color:var(--muted);padding:3px 10px;border-radius:8px;text-decoration:none}
.fb a:hover{background:var(--accent-soft);border-color:var(--accent);color:var(--accent)}
.fb.small{margin-top:6px}.fb.small a{font-size:12px;padding:1px 7px}
.brief{list-style:none;padding:0;margin:0}
.brief li{padding:10px 0;border-bottom:1px solid var(--line)}.brief li:last-child{border-bottom:0}
.brief .t{font-weight:600}.brief .m{color:var(--muted);font-size:13px;margin-left:6px}
code{font-family:ui-monospace,Consolas,monospace;font-size:.9em;background:var(--tag);padding:1px 5px;border-radius:4px}
.list{list-style:none;padding:0}.list li{padding:8px 0;border-bottom:1px solid var(--line)}
footer{margin-top:48px;color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:16px}
"""


def e(text):
    return escape(str(text or ""), quote=True)


def safe_url(url):
    url = str(url or "").strip()
    return url if url.lower().startswith(("http://", "https://")) else ""


def fmt_num(n):
    if n is None:
        return ""
    return f"{n / 10000:.1f} 萬".replace(".0 萬", " 萬") if abs(n) >= 10000 else f"{n:,}"


def metric_tags(item):
    m = item.get("metrics", {})
    src = item.get("source")
    tags = []
    if src == "github_trending" and m.get("stars_today"):
        tags.append((f"今天 +{fmt_num(m['stars_today'])} ⭐", True))
    if src and src.startswith("github") and m.get("stars_delta"):
        tags.append((f"一天 +{fmt_num(m['stars_delta'])} ⭐", True))
    if src and src.startswith("github") and m.get("stars") is not None:
        tags.append((f"總共 {fmt_num(m['stars'])} ⭐", False))
    if src == "hn" and m.get("points") is not None:
        tags.append((f"HN {m['points']} 分", m["points"] >= 200))
    if src == "hf_papers" and m.get("upvotes") is not None:
        tags.append((f"HF {m['upvotes']} 票", m["upvotes"] >= 100))
    if src == "hf_models":
        if m.get("likes_delta"):
            tags.append((f"一天 +{fmt_num(m['likes_delta'])} ♥", True))
        if m.get("downloads") is not None:
            tags.append((f"下載 {fmt_num(m['downloads'])}", False))
    return tags


def deep_link(bot, day, ref, value):
    return f"https://t.me/{bot}?start=fb-{day.replace('-', '')}-{ref}-{value}"


def feedback_html(bot, day, ref, small=False):
    if not bot:
        return ""
    links = "".join(f'<a href="{e(deep_link(bot, day, ref, v))}" target="_blank" rel="noopener">{label}</a>'
                    for v, label in FEEDBACK)
    return f'<div class="fb{" small" if small else ""}">{links}</div>'


def sources_html(sources):
    parts = []
    for s in sources or []:
        url = safe_url(s.get("url"))
        parts.append(f'<a href="{e(url)}" target="_blank" rel="noopener">{e(s.get("label"))}</a>'
                     if url else e(s.get("label")))
    return f'<div class="src">來源：{" · ".join(parts)}</div>' if parts else ""


def tags_html(item):
    tags = [f'<span class="tag{" hot" if hot else ""}">{e(t)}</span>' for t, hot in metric_tags(item)]
    tags += [f'<span class="tag">{e(t)}</span>' for t in item.get("tags", [])]
    if item.get("fallback"):
        tags.insert(0, '<span class="tag hot">原始資料</span>')
    return f'<div class="tags">{"".join(tags)}</div>' if tags else ""


def deep_card(item, bot, day):
    points = "".join(f"<li>{e(p)}</li>" for p in item.get("key_points", []))
    body = [f"<h3>{e(item['title'])}</h3>", tags_html(item)]
    if item.get("summary"):
        body.append(f'<p class="label">摘要</p><p>{e(item["summary"])}</p>')
    if points:
        body.append(f'<p class="label">重點</p><ul>{points}</ul>')
    if item.get("how_to_use"):
        body.append(f'<div class="use"><p class="label">💡 你可以怎麼用</p><p>{e(item["how_to_use"])}</p></div>')
    body.append(sources_html(item.get("sources")))
    body.append(feedback_html(bot, day, item["ref"]))
    return f'<div class="card">{"".join(body)}</div>'


def brief_list(briefs, bot, day):
    if not briefs:
        return ""
    rows = []
    for b in briefs:
        url = safe_url(b.get("url"))
        title = f'<a href="{e(url)}" target="_blank" rel="noopener">{e(b["title"])}</a>' if url else e(b["title"])
        metrics = " · ".join(t for t, _ in metric_tags(b))
        mark = '<span class="tag hot">原始資料</span> ' if b.get("fallback") else ""
        rows.append(f'<li>{mark}<span class="t">{title}</span>'
                    f'{f"<span class=m>{e(metrics)}</span>" if metrics else ""}'
                    f'<div>{e(b.get("one_liner"))}</div>{feedback_html(bot, day, b["ref"], small=True)}</li>')
    return f'<div class="card"><p class="label" style="margin-top:0">快速瀏覽</p><ul class="brief">{"".join(rows)}</ul></div>'


def try_block(t, bot, day):
    steps = "".join(f"<li>{e(s)}</li>" for s in t.get("steps", []))
    parts = [f"<h3>{e(t['title'])}</h3>"]
    if t.get("fallback"):
        parts.append('<div class="tags"><span class="tag hot">原始資料</span></div>')
    parts.append(f"<p>{e(t.get('why'))}</p>")
    if steps:
        parts.append(f"<ol>{steps}</ol>")
    if t.get("success_check"):
        parts.append(f"<p><b>怎樣算成功：</b>{e(t['success_check'])}</p>")
    parts.append(sources_html(t.get("sources")))
    parts.append(feedback_html(bot, day, t["ref"]))
    return f'<section id="try"><h2>🛠️ 今天試一個（約 15～30 分鐘）</h2><div class="card">{"".join(parts)}</div></section>'


def page(title, body):
    return (f'<!DOCTYPE html>\n<html lang="zh-Hant"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(title)}</title><style>{CSS}</style></head>'
            f'<body><div class="wrap">{body}</div></body></html>\n')


def day_label(day):
    d = Date.fromisoformat(day)
    return f"{d.year} 年 {d.month} 月 {d.day} 日（{WEEKDAYS[d.weekday()]}）"


def render_day(digest, bot=""):
    day = digest["date"]
    sections = digest.get("sections", {})
    n_items = sum(len(sections.get(k, {}).get("items", [])) + len(sections.get(k, {}).get("brief", []))
                  for k, _, _ in SECTIONS)
    parts = [f'<header><div class="kicker"><a href="index.html">AI AGENT 早報</a></div>'
             f'<h1>{e(day_label(day))}</h1><div class="meta">約 20 分鐘 · 共 {n_items} 則</div></header>']
    if digest.get("tldr"):
        lis = "".join(f"<li>{e(t)}</li>" for t in digest["tldr"])
        parts.append(f'<div class="tldr"><h2>今天只看三件事的話</h2><ol>{lis}</ol></div>')
    nav = [f'<a href="#{k}">{icon} {e(name)}</a>' for k, icon, name in SECTIONS
           if sections.get(k, {}).get("items") or sections.get(k, {}).get("brief")]
    if digest.get("try_one"):
        nav.append('<a href="#try">🛠️ 今天試一個</a>')
    parts.append(f'<nav>{"".join(nav)}</nav>')
    for key, icon, name in SECTIONS:
        sec = sections.get(key, {})
        if not (sec.get("items") or sec.get("brief")):
            continue
        cards = "".join(deep_card(it, bot, day) for it in sec.get("items", []))
        parts.append(f'<section id="{key}"><h2>{icon} {e(name)}</h2>{cards}{brief_list(sec.get("brief"), bot, day)}</section>')
    if digest.get("try_one"):
        parts.append(try_block(digest["try_one"], bot, day))
    note = "按 👎👍⭐ 會開啟 Telegram，把你的評分傳給早報 bot。" if bot else ""
    parts.append(f'<footer>由 {e(", ".join(digest.get("models_used", [])) or "AI")} 依公開資料整理，'
                 f'內容可能有誤，請以來源為準。{note}<br><a href="index.html">← 所有早報</a></footer>')
    return page(f"AI Agent 早報 {day}", "".join(parts))


def render_index(digests):
    latest = digests[0]
    lis = "".join(f"<li>{e(t)}</li>" for t in latest.get("tldr", []))
    items = "".join(f'<li><a href="{e(d["date"])}.html">{e(day_label(d["date"]))}</a>'
                    f'<div class="meta">{e((d.get("tldr") or [""])[0])}</div></li>' for d in digests)
    body = (f'<header><div class="kicker">AI AGENT 早報</div><h1>每天 9 點的 AI Agent 早報</h1>'
            f'<div class="meta">新聞、新模型、新架構、GitHub 爆紅專案，繁體中文整理</div></header>'
            f'<div class="tldr"><h2>最新：<a href="{e(latest["date"])}.html">{e(day_label(latest["date"]))}</a></h2>'
            f'<ol>{lis}</ol></div><section><h2>所有早報</h2><ul class="list">{items}</ul></section>')
    return page("AI Agent 早報", body)


def render_all(root=".", bot="", out_dir="site"):
    root = Path(root)
    files = sorted((root / "data" / "digest").glob("*.json"), reverse=True)
    if not files:
        return None
    digests = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    site = root / out_dir
    site.mkdir(parents=True, exist_ok=True)
    for d in digests:
        (site / f"{d['date']}.html").write_text(render_day(d, bot), encoding="utf-8")
    (site / "index.html").write_text(render_index(digests), encoding="utf-8")
    return site, [d["date"] for d in digests]
