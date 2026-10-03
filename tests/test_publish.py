import io
import json
import os
import re
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from ai_daily import cli
from ai_daily.publish import collect, html, push
from ai_daily.publish.telegram import Bot, TelegramError

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 30, 1, 0, tzinfo=timezone.utc)
CHAT = "12345"


def card(ref, title, **kw):
    base = {"ref": ref, "source": "github_trending", "id": f"o/{ref}", "title": title, "tags": ["標籤"],
            "summary": "摘要", "key_points": ["重點"], "how_to_use": "用法",
            "metrics": {"stars": 11049, "stars_today": 990, "stars_delta": None},
            "sources": [{"label": "GitHub", "url": f"https://github.com/o/{ref}"}], "fallback": False}
    base.update(kw)
    return base


def digest(day="2026-09-30", **kw):
    d = {
        "date": day, "generated_at": "x", "models_used": ["gemini-3.8-flash"], "llm_calls": 6,
        "tldr": ["第一件", "第二件", "第三件"],
        "sections": {
            "news": {"items": [card("c1", "Dots 發表", source="hn", id="49896604",
                                    metrics={"points": 608, "comments": 472})],
                     "brief": [{"ref": "c2", "source": "hn", "id": "2", "title": "短新聞", "one_liner": "一句",
                                "url": "https://example.com/b", "metrics": {"points": 45}, "fallback": False}]},
            "models": {"items": [], "brief": []},
            "arch": {"items": [card("c5", "TraceDance", source="hf_papers", metrics={"upvotes": 60})], "brief": []},
            "github": {"items": [card("c12", "NVIDIA/OpenShell", id="NVIDIA/OpenShell")], "brief": []},
        },
        "try_one": {"ref": "c12", "source": "github_trending", "id": "NVIDIA/OpenShell", "title": "試 OpenShell",
                    "why": "安全", "steps": ["pip install openshell"], "success_check": "跑起來",
                    "sources": [{"label": "GitHub", "url": "https://github.com/NVIDIA/OpenShell"}],
                    "metrics": {}, "fallback": False},
        "warnings": [],
    }
    d.update(kw)
    return d


class FakeBot:
    def __init__(self, chat_id=CHAT, updates=None, fail=None):
        self.token = "TOKEN123"
        self.chat_id = chat_id
        self.calls = []
        self.updates = list(updates or [])
        self.fail = fail

    def call(self, method, payload):
        self.calls.append((method, payload))
        if self.fail:
            raise self.fail
        if method == "getUpdates":
            off = payload.get("offset")
            return [u for u in self.updates if off is None or u["update_id"] >= off]
        if method == "sendMessage":
            return {"message_id": 77}
        return True

    def mask(self, t):
        return str(t)


def no_network(*a, **k):
    raise AssertionError("network access in tests")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # 用真實 publish.toml 的結構，但 bot_username 固定清空，不受本機設定影響
        cfg = re.sub(r'(?m)^bot_username = ".*"$', 'bot_username = ""',
                     (ROOT / "publish.toml").read_text(encoding="utf-8"))
        cfg = re.sub(r'(?m)^endpoint = ".*"$', 'endpoint = ""', cfg)
        (self.root / "publish.toml").write_text(cfg, encoding="utf-8")
        (self.root / "data" / "digest").mkdir(parents=True)
        self.write_digest(digest())
        for p in (mock.patch.object(urllib.request, "urlopen", side_effect=no_network),
                  mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "", "FEEDBACK_DIR": "",
                                          "FEEDBACK_WEB_KEY": "", "FEEDBACK_READ_KEY": ""})):
            p.start()
            self.addCleanup(p.stop)

    def write_digest(self, d):
        (self.root / "data" / "digest" / f"{d['date']}.json").write_text(json.dumps(d, ensure_ascii=False),
                                                                        encoding="utf-8")

    def cli(self, args, bot=None):
        lines = []
        with mock.patch("builtins.print", side_effect=lambda *a, **k: lines.append(" ".join(map(str, a)))):
            code = cli.main(args + ["--root", str(self.root)], now_utc=NOW,
                            make_bot=(lambda t, c: bot) if bot else None)
        return code, "\n".join(lines)

    def set_bot_username(self, name):
        p = self.root / "publish.toml"
        p.write_text(p.read_text(encoding="utf-8").replace('bot_username = ""', f'bot_username = "{name}"'),
                     encoding="utf-8")


class TestR1DailyPage(Base):
    def test_R1_sections_and_content(self):
        page = html.render_day(digest())
        for text in ("今天只看三件事", "第一件", "AI Agent 新聞", "Dots 發表", "你可以怎麼用", "快速瀏覽",
                     "今天試一個", "pip install openshell", "HN 608 分", "今天 +990 ⭐", "總共 1.1 萬 ⭐"):
            self.assertIn(text, page)
        self.assertNotIn('id="models"', page)  # 空章節不顯示
        self.assertLess(page.index('id="news"'), page.index('id="arch"'))
        self.assertLess(page.index('id="github"'), page.index('id="try"'))
        self.assertIn("prefers-color-scheme:dark", page)
        self.assertIn('name="viewport"', page)

    def test_R1_escaping_and_unsafe_links(self):
        d = digest()
        it = d["sections"]["news"]["items"][0]
        it["title"] = "<script>alert(1)</script>"
        it["sources"] = [{"label": "壞連結", "url": "javascript:alert(1)"}]
        page = html.render_day(d)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("javascript:", page)
        self.assertIn("壞連結", page)

    def test_R1_fallback_marked(self):
        d = digest()
        d["sections"]["news"]["items"][0]["fallback"] = True
        self.assertIn("原始資料", html.render_day(d))

    def test_R1_no_try_one(self):
        page = html.render_day(digest(try_one=None))
        self.assertNotIn('id="try"', page)
        self.assertNotIn("#try", page)


class TestR2Index(Base):
    def test_R2_history_list(self):
        self.write_digest(digest("2026-09-29", tldr=["昨天的事"]))
        code, out = self.cli(["render"])
        self.assertEqual(code, 0)
        site = self.root / "site"
        self.assertTrue((site / "2026-09-29.html").exists())
        self.assertTrue((site / "2026-09-30.html").exists())
        index = (site / "index.html").read_text(encoding="utf-8")
        self.assertIn('最新：<a href="2026-09-30.html"', index)
        self.assertLess(index.index('href="2026-09-30.html">2026'), index.index('href="2026-09-29.html">2026'))

    def test_R2_no_digest(self):
        (self.root / "data" / "digest" / "2026-09-30.json").unlink()
        code, _ = self.cli(["render"])
        self.assertEqual(code, 2)


class TestR3FeedbackLinks(Base):
    def test_R3_deep_link_format(self):
        self.assertEqual(html.deep_link("ai_daily_bot", "2026-09-30", "c12", 1),
                         "https://t.me/ai_daily_bot?start=fb-20260930-c12-1")
        page = html.render_day(digest(), bot="ai_daily_bot")
        for ref in ("c1", "c2", "c5", "c12"):
            for v in (0, 1, 2):
                self.assertIn(f"start=fb-20260930-{ref}-{v}", page)

    def test_R3_no_links_without_username(self):
        self.cli(["render"])
        page = (self.root / "site" / "2026-09-30.html").read_text(encoding="utf-8")
        self.assertNotIn("t.me/", page)
        self.set_bot_username("ai_daily_bot")
        self.cli(["render"])
        page = (self.root / "site" / "2026-09-30.html").read_text(encoding="utf-8")
        self.assertIn("t.me/ai_daily_bot?start=fb-20260930-c12-2", page)


class TestR4Push(Base):
    def test_R4_message_content(self):
        bot = FakeBot()
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": CHAT}):
            code, _ = self.cli(["push", "--date", "2026-09-30"], bot)
        self.assertEqual(code, 0)
        method, payload = bot.calls[0]
        self.assertEqual(method, "sendMessage")
        text = payload["text"]
        for s in ("第一件", "Dots 發表", "TraceDance", "NVIDIA/OpenShell", "試 OpenShell",
                  "https://arku02.github.io/ai-daily/2026-09-30.html"):
            self.assertIn(s, text)
        buttons = payload["reply_markup"]["inline_keyboard"][0]
        self.assertEqual([b["callback_data"] for b in buttons], ["day:20260930:0", "day:20260930:1", "day:20260930:2"])
        rec = json.loads((self.root / "data" / "push" / "2026-09-30.json").read_text(encoding="utf-8"))
        self.assertEqual(rec["message_id"], 77)

    def test_R4_already_pushed(self):
        (self.root / "data" / "push").mkdir(parents=True)
        (self.root / "data" / "push" / "2026-09-30.json").write_text("{}", encoding="utf-8")
        bot = FakeBot()
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": CHAT}):
            code, out = self.cli(["push", "--date", "2026-09-30"], bot)
            self.assertEqual(code, 0)
            self.assertEqual(bot.calls, [])
            self.assertIn("已推送過", out)
            self.cli(["push", "--date", "2026-09-30", "--force"], bot)
        self.assertEqual(len(bot.calls), 1)

    def test_R4_too_long(self):
        d = digest()
        d["sections"]["github"]["items"] = [card(f"c{i}", "很長的標題" * 30) for i in range(100, 160)]
        text = push.build_message(d, "https://x.example/2026-09-30.html")
        self.assertLessEqual(len(text), 4096)
        self.assertIn("https://x.example/2026-09-30.html", text)
        self.assertIn("第一件", text)

    def test_R4_dry_run(self):
        code, out = self.cli(["push", "--date", "2026-09-30", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("day:20260930:2", out)
        self.assertFalse((self.root / "data" / "push").exists())

    def test_R4_html_escaped(self):
        d = digest(tldr=["a < b & c"])
        self.assertIn("a &lt; b &amp; c", push.build_message(d, "https://x"))


class TestR5Credentials(Base):
    def test_R5_missing_token(self):
        code, _ = self.cli(["push", "--date", "2026-09-30"])
        self.assertEqual(code, 2)
        code, _ = self.cli(["collect"])
        self.assertEqual(code, 2)

    def test_R5_token_from_env_file(self):
        (self.root / ".env").write_text("TELEGRAM_BOT_TOKEN=abc\nTELEGRAM_CHAT_ID=999\n", encoding="utf-8")
        seen = {}

        def make(t, c):
            seen.update(token=t, chat=c)
            return FakeBot(chat_id=c)
        with mock.patch("builtins.print"):
            cli.main(["push", "--date", "2026-09-30", "--root", str(self.root)], now_utc=NOW, make_bot=make)
        self.assertEqual(seen, {"token": "abc", "chat": "999"})

    def test_R5_token_masked_and_403_hint(self):
        def post(url, payload, timeout):
            return 403, json.dumps({"ok": False, "description": f"Forbidden: bot was blocked {url}"})
        bot = Bot("SECRET:TOKEN", CHAT, post=post)
        with self.assertRaises(TelegramError) as ctx:
            bot.call("sendMessage", {})
        msg = str(ctx.exception)
        self.assertNotIn("SECRET:TOKEN", msg)
        self.assertIn("***", msg)
        self.assertIn("Start", msg)


def cb(uid, chat, data, cid="q1"):
    return {"update_id": uid, "callback_query": {"id": cid, "data": data, "message": {"chat": {"id": int(chat)}}}}


def msg(uid, chat, text):
    return {"update_id": uid, "message": {"chat": {"id": int(chat)}, "text": text}}


class TestR6Collect(Base):
    def run_collect(self, updates):
        bot = FakeBot(updates=updates)
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": CHAT}):
            code, out = self.cli(["collect"], bot)
        return code, out, bot

    def records(self):
        path = self.root / "feedback" / "feedback.jsonl"
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def test_R6_day_button(self):
        code, out, bot = self.run_collect([cb(10, CHAT, "day:20260930:2")])
        self.assertEqual(code, 0)
        r = self.records()
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["kind"], r[0]["date"], r[0]["value"]), ("day", "2026-09-30", 2))
        answers = [p for m, p in bot.calls if m == "answerCallbackQuery"]
        self.assertIn("已記錄", answers[0]["text"])
        self.assertIn("新增回饋 1 筆", out)

    def test_R6_item_deep_link(self):
        self.run_collect([msg(11, CHAT, "/start fb-20260930-c12-1")])
        r = self.records()[0]
        self.assertEqual((r["kind"], r["value"], r["id"], r["ref"]), ("item", 1, "NVIDIA/OpenShell", "c12"))
        self.assertEqual(r["title"], "NVIDIA/OpenShell")

    def test_R6_unknown_item(self):
        self.run_collect([msg(12, CHAT, "/start fb-20260930-c999-0")])
        self.assertTrue(self.records()[0]["unknown_item"])

    def test_R6_stranger_ignored(self):
        code, _, bot = self.run_collect([msg(13, "999", "/start fb-20260930-c12-2"),
                                         cb(14, "999", "day:20260930:2")])
        self.assertEqual(self.records(), [])
        self.assertFalse(any(m in ("sendMessage", "answerCallbackQuery") for m, _ in bot.calls))
        state = json.loads((self.root / "feedback" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["offset"], 15)

    def test_R6_offset_advances_and_bad_format_skipped(self):
        self.run_collect([msg(20, CHAT, "hello"), cb(21, CHAT, "day:20260930:1")])
        self.assertEqual(len(self.records()), 1)
        # 第二次執行帶上 offset，不重複記錄
        _, _, bot = self.run_collect([msg(20, CHAT, "hello"), cb(21, CHAT, "day:20260930:1")])
        self.assertEqual(bot.calls[0][1]["offset"], 22)
        self.assertEqual(len(self.records()), 1)

    def test_R6_reply_failure_still_records(self):
        class Flaky(FakeBot):
            def call(self, method, payload):
                if method != "getUpdates":
                    raise TelegramError("reply failed")
                return super().call(method, payload)
        bot = Flaky(updates=[cb(30, CHAT, "day:20260930:0")])
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": CHAT}):
            self.cli(["collect"], bot)
        self.assertEqual(len(self.records()), 1)


class TestR7FeedbackLocation(Base):
    def test_R7_env_override(self):
        other = self.root / "private-repo"
        bot = FakeBot(updates=[cb(1, CHAT, "day:20260930:1")])
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": CHAT,
                                          "FEEDBACK_DIR": str(other)}):
            self.cli(["collect"], bot)
        self.assertTrue((other / "feedback.jsonl").exists())
        self.assertTrue((other / "state.json").exists())
        self.assertFalse((self.root / "feedback").exists())

    def test_R7_gitignored(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("feedback/", lines)
        self.assertIn("site/", lines)


EP = "https://fb.example.workers.dev"
WEB_KEY = "abcDEF123456789xyz"
READ_KEY = "read-0123456789abcdef"


def set_endpoint(root, url):
    p = root / "publish.toml"
    p.write_text(re.sub(r'(?m)^endpoint = ".*"$', f'endpoint = "{url}"', p.read_text(encoding="utf-8")),
                 encoding="utf-8")


class TestR3DirectMode(Base):
    def render(self):
        self.assertEqual(self.cli(["render"])[0], 0)
        site = self.root / "site"
        return ((site / "2026-09-30.html").read_text(encoding="utf-8"),
                (site / "index.html").read_text(encoding="utf-8"))

    def test_R3_direct_mode_markup(self):
        self.set_bot_username("ai_daily_bot")
        set_endpoint(self.root, EP + "/")
        page, index = self.render()
        self.assertIn('href="https://t.me/ai_daily_bot?start=fb-20260930-c12-1" '
                      'data-day="2026-09-30" data-ref="c12" data-v="1"', page)
        for ref in ("c1", "c2", "c5", "c12"):
            self.assertIn(f'data-ref="{ref}" data-v="2"', page)
        for text in (page, index):
            self.assertIn(f'var EP="{EP}"', text)
            self.assertIn('id="fbtoast"', text)
        self.assertIn('id="fbnote"', page)

    def test_R3_endpoint_not_https(self):
        self.set_bot_username("ai_daily_bot")
        for bad in ("", "javascript:alert(1)", "http://fb.example.workers.dev", 'https://x.dev/\\";alert(1)//'):
            set_endpoint(self.root, bad)
            page, index = self.render()
            for text in (page, index):
                self.assertNotIn("data-ref=", text, bad)
                self.assertNotIn("<script", text, bad)
            self.assertIn("start=fb-20260930-c12-1", page)

    def test_R3_endpoint_without_bot(self):
        set_endpoint(self.root, EP)
        page, index = self.render()
        for text in (page, index):
            self.assertNotIn("<script", text)
            self.assertNotIn("t.me/", text)

    def test_R3_script_pass_and_fallback(self):
        js = html.SUBMIT_JS
        self.assertIn("#k=", js)
        self.assertIn("history.replaceState", js)
        # 沒有通行證就直接 return，讓 deep link 照常開啟；有通行證才阻止跳轉
        self.assertLess(js.index("if(!key)return"), js.index("ev.preventDefault()"))
        self.assertIn('EP+"/feedback"', js)
        self.assertIn('"Authorization":"Bearer "+key', js)
        self.assertIn("r.status===401){put(K,null)", js)
        self.assertIn("box.classList.add(\"err\")", js)


class TestR9PassLink(Base):
    def run_pass(self, bot, key=WEB_KEY):
        env = {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": CHAT, "FEEDBACK_WEB_KEY": key}
        with mock.patch.dict(os.environ, env):
            return self.cli(["pass-link"], bot)

    def test_R9_link_sent(self):
        bot = FakeBot()
        code, out = self.run_pass(bot)
        self.assertEqual(code, 0)
        sent = [p for m, p in bot.calls if m == "sendMessage"]
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["chat_id"], CHAT)
        self.assertIn(f"https://arku02.github.io/ai-daily/index.html#k={WEB_KEY}", sent[0]["text"])
        self.assertTrue(sent[0]["link_preview_options"]["is_disabled"])
        self.assertNotIn(WEB_KEY, out)

    def test_R9_missing_pass_key(self):
        bot = FakeBot()
        code, out = self.run_pass(bot, key="")
        self.assertEqual(code, 2)
        self.assertIn("FEEDBACK_WEB_KEY", out)
        self.assertIn(".env", out)
        self.assertEqual(bot.calls, [])

    def test_R9_error_masked(self):
        code, out = self.run_pass(FakeBot(fail=TelegramError(f"failed for {WEB_KEY}")))
        self.assertEqual(code, 1)
        self.assertNotIn(WEB_KEY, out)


class FakeGet:
    def __init__(self, pages=None, fail=None):
        self.pages = list(pages or [])
        self.fail = fail
        self.calls = []

    def __call__(self, url, key):
        self.calls.append((url, key))
        if self.fail:
            raise self.fail
        return {"items": self.pages.pop(0) if self.pages else []}


def row(i, ref="c12", value=2, day="2026-09-30"):
    return {"id": i, "received_at": "2026-09-30T02:03:04Z", "date": day, "ref": ref, "value": value}


class TestR10CollectWeb(Base):
    def setUp(self):
        super().setUp()
        set_endpoint(self.root, EP)

    def run_collect(self, get, updates=(), key=READ_KEY):
        bot = FakeBot(updates=list(updates))
        env = {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": CHAT, "FEEDBACK_READ_KEY": key}
        with mock.patch.dict(os.environ, env), mock.patch.object(collect, "http_get_json", get):
            return self.cli(["collect"], bot)

    def records(self):
        path = self.root / "feedback" / "feedback.jsonl"
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def state(self):
        return json.loads((self.root / "feedback" / "state.json").read_text(encoding="utf-8"))

    def test_R10_web_ratings_collected(self):
        get = FakeGet([[row(4)]])
        code, out = self.run_collect(get, [cb(7, CHAT, "day:20260930:1")])
        self.assertEqual(code, 0)
        self.assertEqual(get.calls, [(f"{EP}/feedback?after=0", READ_KEY)])
        web = [r for r in self.records() if r.get("via") == "web"]
        self.assertEqual(len(self.records()), 2)
        self.assertEqual(len(web), 1)
        w = web[0]
        self.assertEqual((w["kind"], w["value"], w["id"], w["ref"], w["date"]),
                         ("item", 2, "NVIDIA/OpenShell", "c12", "2026-09-30"))
        self.assertEqual(w["received_at"], "2026-09-30T02:03:04Z")
        self.assertEqual(self.state(), {"offset": 8, "web_after": 4})
        self.assertIn("新增網頁回饋 1 筆", out)
        # 第二次從 web_after 接著拉，不重複
        get2 = FakeGet([])
        self.run_collect(get2)
        self.assertEqual(get2.calls[0][0], f"{EP}/feedback?after=4")
        self.assertEqual(len(self.records()), 2)

    def test_R10_paging_bad_rows_and_unknown(self):
        first = [row(i, ref="c1", value=i % 3) for i in range(1, 501)]
        second = [row(501, ref="zz"), row(502, value=7), row(503, value=True), row(504, day="20260930"),
                  row(505, ref="c999")]
        get = FakeGet([first, second])
        code, _ = self.run_collect(get)
        self.assertEqual(code, 0)
        self.assertEqual([u for u, _ in get.calls], [f"{EP}/feedback?after=0", f"{EP}/feedback?after=500"])
        recs = self.records()
        self.assertEqual(len(recs), 501)
        self.assertTrue(recs[-1]["unknown_item"])
        self.assertEqual(recs[-1]["ref"], "c999")
        self.assertEqual(self.state()["web_after"], 505)

    def test_R10_missing_read_key(self):
        get = FakeGet([[row(1)]])
        code, out = self.run_collect(get, [cb(3, CHAT, "day:20260930:2")], key="")
        self.assertEqual(code, 1)
        self.assertIn("FEEDBACK_READ_KEY", out)
        self.assertEqual([r["kind"] for r in self.records()], ["day"])
        self.assertEqual(get.calls, [])

    def test_R10_worker_error_masked(self):
        err = urllib.error.HTTPError(f"{EP}/feedback", 500, "boom", {},
                                     io.BytesIO(f"internal error {READ_KEY}".encode()))
        with mock.patch.object(urllib.request, "urlopen", side_effect=err):
            code, out = self.run_collect(collect.http_get_json, [cb(5, CHAT, "day:20260930:0")])
        self.assertEqual(code, 1)
        self.assertIn("HTTP 500", out)
        self.assertIn("***", out)
        self.assertNotIn(READ_KEY, out)
        self.assertEqual(len(self.records()), 1)

    def test_R10_partial_progress_kept_on_error(self):
        class Flaky(FakeGet):
            def __call__(self, url, key):
                if self.calls:
                    self.calls.append((url, key))
                    raise collect.WebFeedbackError("timeout")
                return super().__call__(url, key)
        get = Flaky([[row(i) for i in range(1, 501)]])
        code, _ = self.run_collect(get)
        self.assertEqual(code, 1)
        self.assertEqual(len(self.records()), 500)
        self.assertEqual(self.state()["web_after"], 500)

    def test_R10_no_endpoint_no_call(self):
        set_endpoint(self.root, "")
        get = FakeGet(fail=AssertionError("不應呼叫 Worker"))
        code, out = self.run_collect(get, key="")
        self.assertEqual(code, 0)
        self.assertEqual(get.calls, [])
        self.assertNotIn("網頁回饋", out)


class TestD1Offline(Base):
    def test_D1_full_flow_without_network(self):
        self.set_bot_username("ai_daily_bot")
        bot = FakeBot(updates=[cb(1, CHAT, "day:20260930:1"), msg(2, CHAT, "/start fb-20260930-c1-2")])
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": CHAT}):
            self.assertEqual(self.cli(["render"])[0], 0)
            self.assertEqual(self.cli(["push", "--date", "2026-09-30"], bot)[0], 0)
            self.assertEqual(self.cli(["collect"], bot)[0], 0)
        feedback = (self.root / "feedback" / "feedback.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(feedback), 2)

    def test_D1_test_file_registered(self):
        cfg = json.loads((ROOT / "workflow.config.json").read_text(encoding="utf-8"))
        self.assertIn("tests/test_publish.py", cfg["testFiles"])


if __name__ == "__main__":
    unittest.main()
