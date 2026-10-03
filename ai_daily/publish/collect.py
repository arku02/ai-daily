"""R6～R7、R10：從 Telegram 與網頁評分端點（Cloudflare Worker）收回饋，寫入回饋資料夾（私人 repo）。"""

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .telegram import TelegramError

DAY_RE = re.compile(r"^day:(\d{8}):([012])$")
ITEM_RE = re.compile(r"^/start fb-(\d{8})-(c\d{1,4})-([012])$")
WEB_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEB_REF_RE = re.compile(r"^c\d{1,4}$")
WEB_PAGE = 500
ITEM_LABELS = {0: "👎 沒興趣", 1: "👍 有用", 2: "⭐ 超有用"}
DAY_LABELS = {0: "👎 今天沒料", 1: "👍 有用", 2: "⭐ 很有收穫"}


def iso_day(compact):
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"


def find_item(root, day, ref):
    path = Path(root) / "data" / "digest" / f"{day}.json"
    if not path.is_file():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    pool = [x for s in d.get("sections", {}).values() for x in s.get("items", []) + s.get("brief", [])]
    if d.get("try_one"):
        pool.append(d["try_one"])
    for x in pool:
        if x.get("ref") == ref:
            return {"source": x.get("source"), "id": x.get("id"), "title": x.get("title")}
    return None


def load_state(folder):
    path = folder / "state.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"offset": None}


def collect(bot, root, folder, now=None, out=None):
    out = out or (lambda *a: print(*a))
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    state = load_state(folder)
    records = []
    max_id = None
    while True:
        payload = {"timeout": 0, "limit": 100, "allowed_updates": ["message", "callback_query"]}
        if state.get("offset") is not None:
            payload["offset"] = state["offset"]
        updates = bot.call("getUpdates", payload) or []
        if not updates:
            break
        for u in updates:
            max_id = u["update_id"] if max_id is None else max(max_id, u["update_id"])
            rec = handle(bot, root, u, now)
            if rec:
                records.append(rec)
        state["offset"] = max_id + 1
        if len(updates) < 100:
            break
    if records:
        with (folder / "feedback.jsonl").open("a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if max_id is not None:
        (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
    out(f"新增回饋 {len(records)} 筆 → {(folder / 'feedback.jsonl').as_posix()}")
    return records


class WebFeedbackError(Exception):
    pass


def http_get_json(url, key, timeout=30):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "User-Agent": "ai-daily/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise WebFeedbackError(f"HTTP {e.code} {e.read().decode('utf-8', errors='replace')[:200]}") from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        raise WebFeedbackError(f"{type(e).__name__}: {e}") from None


def collect_web(root, folder, endpoint, key, get=http_get_json, out=None):
    """R10：以讀取金鑰從 Worker 拉 id 大於 web_after 的評分，附加到 feedback.jsonl。"""
    out = out or (lambda *a: print(*a))
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    state = load_state(folder)
    after = int(state.get("web_after") or 0)
    records = []
    try:
        while True:
            data = get(f"{endpoint.rstrip('/')}/feedback?after={after}", key)
            items = data.get("items") if isinstance(data, dict) else None
            if not isinstance(items, list):
                raise WebFeedbackError("回應格式不符：缺少 items")
            for it in items:
                try:
                    after = max(after, int(it["id"]))
                except (KeyError, TypeError, ValueError):
                    raise WebFeedbackError("回應格式不符：缺少 id") from None
                rec = web_record(root, it)
                if rec:
                    records.append(rec)
            if len(items) < WEB_PAGE:
                break
    except WebFeedbackError as e:
        raise WebFeedbackError(f"網頁回饋收集失敗：{e}".replace(key, "***")) from None
    finally:
        if records:
            with (folder / "feedback.jsonl").open("a", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        if after != int(state.get("web_after") or 0):
            state["web_after"] = after
            (folder / "state.json").write_text(json.dumps(state), encoding="utf-8")
    out(f"新增網頁回饋 {len(records)} 筆 → {(folder / 'feedback.jsonl').as_posix()}")
    return records


def web_record(root, it):
    day, ref, value = it.get("date"), it.get("ref"), it.get("value")
    if not (isinstance(day, str) and WEB_DAY_RE.match(day) and isinstance(ref, str) and WEB_REF_RE.match(ref)
            and value in (0, 1, 2) and not isinstance(value, bool)):
        return None
    rec = {"received_at": str(it.get("received_at") or ""), "kind": "item", "date": day, "value": value,
           "ref": ref, "via": "web"}
    info = find_item(root, day, ref)
    if info:
        rec.update(info)
    else:
        rec["unknown_item"] = True
    return rec


def _reply(bot, method, payload):
    """回覆失敗不影響記錄回饋。"""
    try:
        bot.call(method, payload)
    except TelegramError:
        pass


def handle(bot, root, update, now=None):
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cq = update.get("callback_query")
    if cq:
        chat = str(((cq.get("message") or {}).get("chat") or {}).get("id"))
        m = DAY_RE.match(cq.get("data") or "")
        if chat != bot.chat_id or not m:
            return None
        value = int(m.group(2))
        _reply(bot, "answerCallbackQuery", {"callback_query_id": cq["id"], "text": f"已記錄：{DAY_LABELS[value]}"})
        return {"received_at": stamp, "kind": "day", "date": iso_day(m.group(1)), "value": value}
    msg = update.get("message")
    if msg:
        chat = str((msg.get("chat") or {}).get("id"))
        m = ITEM_RE.match((msg.get("text") or "").strip())
        if chat != bot.chat_id or not m:
            return None
        day, ref, value = iso_day(m.group(1)), m.group(2), int(m.group(3))
        info = find_item(root, day, ref)
        rec = {"received_at": stamp, "kind": "item", "date": day, "value": value, "ref": ref}
        if info:
            rec.update(info)
        else:
            rec["unknown_item"] = True
        title = info["title"] if info else ref
        _reply(bot, "sendMessage", {"chat_id": bot.chat_id, "text": f"已記錄：{ITEM_LABELS[value]}｜{title}",
                                    "disable_notification": True})
        return rec
    return None
