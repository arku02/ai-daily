"""以 Node 載入真實的 worker/src/index.js 測試網頁評分端點（記憶體 D1，不連網）。"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "worker" / "test" / "harness.mjs"
WEB, READ = "web-pass-0123456789", "read-key-0123456789"
ENV = {"WEB_KEY": WEB, "READ_KEY": READ, "ALLOWED_ORIGIN": "https://arku02.github.io",
       "SITE_URL": "https://arku02.github.io/ai-daily/"}
PAGE = '<a data-day="2026-09-30" data-ref="c12" data-v="1">x</a><a data-ref="c1">y</a>'
AUTH = {"Authorization": f"Bearer {WEB}", "Content-Type": "application/json"}


def run(requests, pages=None, rows=None, limit=None, env=None, now=None):
    node = shutil.which("node")
    assert node, "需要 Node 才能測試 Worker"
    data = {"env": ENV if env is None else env, "pages": {"2026-09-30": PAGE} if pages is None else pages,
            "rows": rows or [], "limit": limit, "requests": requests}
    if now:
        data["now"] = now
    p = subprocess.run([node, str(HARNESS)], input=json.dumps(data), capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def post(body, headers=AUTH):
    return {"method": "POST", "path": "/feedback", "headers": headers, "body": body}


GOOD = {"date": "2026-09-30", "ref": "c12", "value": 1}


class TestR8Endpoint(unittest.TestCase):
    def test_R8_valid_rating_stored(self):
        out = run([post(GOOD)])
        r = out["responses"][0]
        self.assertEqual(r["status"], 200)
        self.assertEqual(r["headers"]["access-control-allow-origin"], "https://arku02.github.io")
        self.assertEqual(len(out["rows"]), 1)
        row = out["rows"][0]
        self.assertEqual((row["id"], row["date"], row["ref"], row["value"]), (1, "2026-09-30", "c12", 1))
        self.assertRegex(row["received_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(out["fetched"], ["https://arku02.github.io/ai-daily/2026-09-30.html"])

    def test_R8_no_pass_rejected(self):
        out = run([post(GOOD, {"Content-Type": "application/json"}),
                   post(GOOD, {"Authorization": "Bearer wrong", "Content-Type": "application/json"}),
                   post(GOOD, {"Authorization": f"Bearer {READ}"})])
        self.assertEqual([r["status"] for r in out["responses"]], [401, 401, 401])
        self.assertEqual(out["rows"], [])
        self.assertEqual(out["fetched"], [], "未驗證的請求不應觸發抓取網頁")

    def test_R8_missing_web_key_fails_closed(self):
        env = dict(ENV, WEB_KEY="")
        out = run([post(GOOD, {"Authorization": "Bearer "})], env=env)
        self.assertEqual(out["responses"][0]["status"], 401)

    def test_R8_bad_content_rejected(self):
        bad = [dict(GOOD, value=5), dict(GOOD, value="1"), dict(GOOD, value=True), dict(GOOD, ref="x1"),
               dict(GOOD, ref="c12345"), dict(GOOD, date="2026-02-30"), dict(GOOD, date="2026/09/30"),
               dict(GOOD, date="2026-07-01"), dict(GOOD, date="2026-10-02"), "not json", ["array"]]
        out = run([post(b) for b in bad])
        self.assertEqual([r["status"] for r in out["responses"]], [400] * len(bad))
        self.assertEqual(out["rows"], [])

    def test_R8_date_window(self):
        pages = {"2026-08-01": PAGE, "2026-10-01": PAGE}
        out = run([post(dict(GOOD, date="2026-08-01")), post(dict(GOOD, date="2026-10-01"))], pages=pages)
        self.assertEqual([r["status"] for r in out["responses"]], [200, 200])

    def test_R8_too_large(self):
        out = run([post(dict(GOOD, pad="x" * 2000))])
        self.assertEqual(out["responses"][0]["status"], 413)

    def test_R8_unknown_item_rejected(self):
        out = run([post(dict(GOOD, ref="c999")), post(dict(GOOD, ref="c2")),
                   post(dict(GOOD, date="2026-09-29"))])
        self.assertEqual([r["status"] for r in out["responses"]], [404, 404, 404])
        self.assertEqual(out["rows"], [])

    def test_R8_site_unavailable(self):
        out = run([post(GOOD)], pages={"2026-09-30": 502})
        self.assertEqual(out["responses"][0]["status"], 503)
        self.assertEqual(out["rows"], [])

    def test_R8_rate_limited(self):
        out = run([post(GOOD)] * 21, limit=20)
        statuses = [r["status"] for r in out["responses"]]
        self.assertEqual(statuses[:20], [200] * 20)
        self.assertEqual(statuses[20], 429)
        self.assertEqual(len(out["rows"]), 20)

    def test_R8_rate_limit_before_auth(self):
        bad = {"Authorization": "Bearer guess", "Content-Type": "application/json"}
        out = run([post(GOOD, bad)] * 3, limit=2)
        self.assertEqual([r["status"] for r in out["responses"]], [401, 401, 429])

    def test_R8_cors_preflight(self):
        out = run([{"method": "OPTIONS", "path": "/feedback"}])
        r = out["responses"][0]
        self.assertEqual(r["status"], 204)
        self.assertEqual(r["headers"]["access-control-allow-origin"], "https://arku02.github.io")
        self.assertIn("Authorization", r["headers"]["access-control-allow-headers"])

    def test_R8_read_with_read_key(self):
        rows = [{"id": i, "received_at": "2026-09-30T01:00:00Z", "date": "2026-09-30", "ref": "c12", "value": 1}
                for i in (1, 2, 3)]
        out = run([{"path": "/feedback?after=1", "headers": {"Authorization": f"Bearer {READ}"}},
                   {"path": "/feedback", "headers": {"Authorization": f"Bearer {READ}"}},
                   {"path": "/feedback?after=1", "headers": {"Authorization": f"Bearer {WEB}"}},
                   {"path": "/feedback"}], rows=rows)
        r = out["responses"]
        self.assertEqual(r[0]["status"], 200)
        self.assertEqual([x["id"] for x in r[0]["body"]["items"]], [2, 3])
        self.assertEqual([x["id"] for x in r[1]["body"]["items"]], [1, 2, 3])
        self.assertEqual([r[2]["status"], r[3]["status"]], [401, 401])

    def test_R8_read_page_size(self):
        rows = [{"id": i, "received_at": "x", "date": "2026-09-30", "ref": "c1", "value": 0} for i in range(1, 503)]
        out = run([{"path": "/feedback", "headers": {"Authorization": f"Bearer {READ}"}}], rows=rows)
        items = out["responses"][0]["body"]["items"]
        self.assertEqual((len(items), items[-1]["id"]), (500, 500))

    def test_R8_other_paths_and_methods(self):
        out = run([{"path": "/"}, {"method": "PUT", "path": "/feedback", "body": "{}"},
                   {"method": "DELETE", "path": "/feedback"}])
        self.assertEqual([r["status"] for r in out["responses"]], [404, 405, 405])


class TestD1Config(unittest.TestCase):
    def test_D1_wrangler_config(self):
        text = (ROOT / "worker" / "wrangler.toml").read_text(encoding="utf-8")
        self.assertIn('binding = "DB"', text)
        self.assertRegex(text, r'(?s)\[\[ratelimits\]\]\s*name = "LIMITER".*limit = 20\s*period = 60')
        self.assertIn('ALLOWED_ORIGIN = "https://arku02.github.io"', text)
        self.assertNotRegex(text, r"(?m)^\s*(WEB_KEY|READ_KEY)\s*=")

    def test_D1_collect_workflow_secret(self):
        text = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
        step = re.search(r"(?s)- name: Collect\n(.*?)run: python -m ai_daily collect", text).group(1)
        self.assertIn("FEEDBACK_READ_KEY: ${{ secrets.FEEDBACK_READ_KEY }}", step)

    def test_D1_test_file_registered(self):
        cfg = json.loads((ROOT / "workflow.config.json").read_text(encoding="utf-8"))
        self.assertIn("tests/test_worker.py", cfg["testFiles"])


if __name__ == "__main__":
    unittest.main()
