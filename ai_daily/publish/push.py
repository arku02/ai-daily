"""R4：組裝並推送 Telegram 重點訊息。"""

import json
from datetime import date as Date
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .html import SECTIONS, WEEKDAYS

LIMIT = 4096
DAY_BUTTONS = [(0, "👎 今天沒料"), (1, "👍 有用"), (2, "⭐ 很有收穫")]


def page_url(base_url, day):
    return base_url.rstrip("/") + f"/{day}.html"


def _e(text):
    return escape(str(text or ""), quote=False)


def build_message(digest, url):
    d = Date.fromisoformat(digest["date"])
    head = [f"☀️ <b>AI Agent 早報｜{d.month}/{d.day}（{WEEKDAYS[d.weekday()]}）</b>", ""]
    if digest.get("tldr"):
        head.append("<b>今天三件事</b>")
        head += [f"{i}. {_e(t)}" for i, t in enumerate(digest["tldr"], 1)]
        head.append("")
    # 每個章節的標題清單；超過長度時從最後面開始刪
    blocks = []
    for key, icon, name in SECTIONS:
        titles = [it["title"] for it in digest.get("sections", {}).get(key, {}).get("items", [])]
        if titles:
            blocks.append([f"{icon} <b>{_e(name)}</b>"] + [f"• {_e(t)}" for t in titles])
    tail = [""]
    if digest.get("try_one"):
        tail.append(f"🛠️ 今天試一個：{_e(digest['try_one']['title'])}")
    tail.append(f'👉 <a href="{_e(url)}">完整版（約 20 分鐘）</a>')

    def compose():
        body = []
        for b in blocks:
            if len(b) > 1:
                body += b + [""]
        return "\n".join(head + body + tail).replace("\n\n\n", "\n\n").strip()

    text = compose()
    while len(text) > LIMIT and any(len(b) > 1 for b in blocks):
        last = max(i for i, b in enumerate(blocks) if len(b) > 1)
        blocks[last].pop()
        text = compose()
    if len(text) > LIMIT:  # 三件事本身太長：只留網址與日期
        head = head[:2]
        text = compose()
    return text


def keyboard(day):
    compact = day.replace("-", "")
    return {"inline_keyboard": [[{"text": label, "callback_data": f"day:{compact}:{v}"} for v, label in DAY_BUTTONS]]}


def record_path(root, day):
    return Path(root) / "data" / "push" / f"{day}.json"


def push(bot, digest, base_url, root, force=False, dry_run=False, out=None, now=None):
    out = out or (lambda *a: print(*a))
    day = digest["date"]
    url = page_url(base_url, day)
    text = build_message(digest, url)
    rec = record_path(root, day)
    if dry_run:
        out(text)
        out(f"[按鈕] {' / '.join(b['text'] + '=' + b['callback_data'] for b in keyboard(day)['inline_keyboard'][0])}")
        out(f"（dry-run：{len(text)} 字元，沒有送出）")
        return 0
    if rec.exists() and not force:
        out(f"{day} 已推送過（{rec.as_posix()}），要重送請加 --force")
        return 0
    result = bot.call("sendMessage", {"chat_id": bot.chat_id, "text": text, "parse_mode": "HTML",
                                      "disable_web_page_preview": True, "reply_markup": keyboard(day)})
    rec.parent.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc)
    rec.write_text(json.dumps({"date": day, "message_id": (result or {}).get("message_id"),
                               "pushed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "url": url},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    out(f"已推送 {day}（{len(text)} 字元）→ {url}")
    return 0
