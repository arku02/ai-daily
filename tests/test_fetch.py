import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from ai_daily import cli, http, pipeline
from ai_daily.model import normalize_url
from ai_daily.sources import github, hf, hn, rss

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures"
NOW = datetime(2026, 9, 30, 1, 0, tzinfo=timezone.utc)  # 台北 9/30 09:00
RUN_DATE = date(2026, 9, 30)

RSS_XML = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Fresh post</title><link>https://example.com/fresh?utm_source=rss</link>
<description>&lt;p&gt;Hello &lt;b&gt;agents&lt;/b&gt;&lt;/p&gt;</description>
<pubDate>Tue, 29 Sep 2026 20:00:00 GMT</pubDate></item>
<item><title>Old post</title><link>https://example.com/old</link>
<pubDate>Mon, 21 Sep 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM_XML = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>a</title>
<entry><title>Atom entry</title><link rel="alternate" href="https://atom.example.com/e1"/>
<updated>2026-09-29T12:00:00Z</updated><summary>Short</summary></entry></feed>"""


def fixture(name):
    return (FIX / name).read_text(encoding="utf-8")


class FakeHTTP:
    """依網址回傳 fixture；fail 裡的關鍵字會丟出 FetchError。"""

    def __init__(self, fail=()):
        self.fail = fail
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        for key in self.fail:
            if key in url:
                raise http.FetchError(f"HTTP 503 {url}")
        if "hn.algolia.com" in url:
            return fixture("hn.json")
        if "huggingface.co/api/models" in url:
            return fixture("hf_models.json")
        if "huggingface.co/api/daily_papers" in url:
            return fixture("hf_papers.json")
        if "api.github.com/search" in url:
            return fixture("gh_search.json")
        if "github.com/trending" in url:
            return fixture("gh_trending.html")
        if "atom" in url:
            return ATOM_XML
        if "feed" in url or "rss" in url:
            return RSS_XML
        raise AssertionError(f"unexpected url {url}")


def config():
    return {
        "github_trending": {"urls": ["https://github.com/trending?since=daily"]},
        "github_search": {"queries": ["agent"], "created_within_days": 14},
        "hf_models": {"pipelines": ["text-generation", "image-text-to-text"]},
        "hf_papers": {"days_back": 1, "min_upvotes": 0},
        "hn": {"keywords": ["agent"], "min_points": 30, "window_hours": 36},
        "rss": {"window_hours": 36, "feeds": [
            {"name": "Feed", "url": "https://example.com/feed"},
            {"name": "Atom", "url": "https://example.com/atom"},
        ]},
    }


def ctx():
    return pipeline.Context(date=RUN_DATE, now=NOW)


def no_network(*a, **k):
    raise AssertionError("network access in tests")


class Base(unittest.TestCase):
    def setUp(self):
        self.fake = FakeHTTP()
        patches = [
            mock.patch.object(http, "get_text", side_effect=lambda u: self.fake(u)),
            mock.patch.object(urllib.request, "urlopen", side_effect=no_network),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)

    def run_pipeline(self, cfg=None, when=NOW, day=RUN_DATE):
        c = pipeline.Context(date=day, now=when)
        return pipeline.run(cfg or config(), c, self.out)


class TestR1UnifiedFormat(Base):
    def test_R1_hn_story_becomes_item(self):
        items = {i.id: i for i in hn.fetch(config()["hn"], ctx())}
        item = items["49896604"]
        self.assertEqual(item.source, "hn")
        self.assertEqual(item.metrics["points"], 608)
        self.assertEqual(item.metrics["comments"], 472)
        self.assertEqual(item.extra["discussion"], "https://news.ycombinator.com/item?id=49896604")
        self.assertRegex(item.published_at, r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

    def test_R1_hn_story_without_url(self):
        items = {i.id: i for i in hn.fetch(config()["hn"], ctx())}
        self.assertEqual(items["49900001"].url, "https://news.ycombinator.com/item?id=49900001")

    def test_R1_every_source_uses_unified_fields(self):
        report, _, _ = self.run_pipeline()
        fields = {"source", "id", "title", "url", "summary", "published_at", "metrics", "extra", "also_in"}
        sources = set()
        for it in report["items"]:
            self.assertEqual(set(it), fields)
            self.assertTrue(it["id"] and it["url"])
            for v in it["metrics"].values():
                self.assertTrue(v is None or isinstance(v, (int, float)))
            sources.add(it["source"])
        self.assertEqual(sources, {"github_trending", "github_search", "hf_models", "hf_papers", "hn", "rss"})

    def test_R1_trending_parsed_from_real_page(self):
        items = {i.id: i for i in github.parse_trending(fixture("gh_trending.html"))}
        self.assertIn("NVIDIA/OpenShell", items)
        self.assertEqual(items["NVIDIA/OpenShell"].metrics["stars_today"], 990)
        self.assertIsInstance(items["NVIDIA/OpenShell"].metrics["stars"], int)
        self.assertEqual(items["vectorize-io/hindsight"].extra["language"], "Python")


class TestR2Filters(Base):
    def test_R2_hn_points_threshold(self):
        ids = {i.id for i in hn.fetch(config()["hn"], ctx())}
        self.assertIn("49896604", ids)
        self.assertNotIn("49900002", ids)  # 12 分

    def test_R2_disabled_source_makes_no_request(self):
        cfg = config()
        cfg["rss"]["enabled"] = False
        report, _, _ = self.run_pipeline(cfg)
        self.assertEqual(report["sources"]["rss"]["status"], "disabled")
        self.assertFalse(any("example.com" in u for u in self.fake.urls))

    def test_R2_hf_pipeline_filter(self):
        ids = {i.id for i in hf.fetch_models(config()["hf_models"], ctx())}
        self.assertIn("deepseek-ai/DeepSeek-V4.1-Flash", ids)
        self.assertNotIn("Qwen/Qwen-Image-2.1", ids)  # text-to-image

    def test_R2_github_search_created_window(self):
        github.fetch_search(config()["github_search"], ctx())
        self.assertTrue(any("created:>2026-09-16" in u for u in self.fake.urls))

    def test_R2_papers_date_and_min_upvotes(self):
        items = hf.fetch_papers({"days_back": 1, "min_upvotes": 100}, ctx())
        self.assertTrue(any("date=2026-09-29" in u for u in self.fake.urls))
        self.assertEqual([i.id for i in items], ["2609.32577"])

    def test_R2_rss_window(self):
        items = rss.fetch(config()["rss"], ctx())
        titles = {i.title for i in items}
        self.assertEqual(titles, {"Fresh post", "Atom entry"})
        fresh = next(i for i in items if i.title == "Fresh post")
        self.assertEqual(fresh.summary, "Hello agents")


class TestR3Growth(Base):
    def write_snap(self, day, data):
        d = self.out / "snapshots"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{day}.json").write_text(json.dumps(data), encoding="utf-8")

    def item(self, report, source, iid):
        for it in report["items"]:
            if it["source"] == source and it["id"] == iid:
                return it
            for other in it["also_in"]:
                if other["source"] == source and other["id"] == iid:
                    return other
        raise AssertionError(f"{source} {iid} missing")

    def current_stars(self, repo):
        return {i.id: i for i in github.parse_trending(fixture("gh_trending.html"))}[repo].metrics["stars"]

    def test_R3_delta_from_previous_snapshot(self):
        stars = self.current_stars("NVIDIA/OpenShell")
        self.write_snap("2026-09-29", {"github": {"NVIDIA/OpenShell": stars - 300},
                                       "hf_models": {"deepseek-ai/DeepSeek-V4.1-Flash": 3000}})
        report, _, _ = self.run_pipeline()
        self.assertEqual(self.item(report, "github_trending", "NVIDIA/OpenShell")["metrics"]["stars_delta"], 300)
        likes = self.item(report, "hf_models", "deepseek-ai/DeepSeek-V4.1-Flash")["metrics"]
        self.assertEqual(likes["likes_delta"], likes["likes"] - 3000)
        snap = json.loads((self.out / "snapshots" / "2026-09-30.json").read_text(encoding="utf-8"))
        self.assertEqual(snap["github"]["NVIDIA/OpenShell"], stars)

    def test_R3_first_time_seen_is_null(self):
        self.write_snap("2026-09-29", {"github": {}})
        report, _, _ = self.run_pipeline()
        m = self.item(report, "github_trending", "vectorize-io/hindsight")["metrics"]
        self.assertIsNone(m["stars_delta"])
        self.assertIsNotNone(m["stars_today"])

    def test_R3_no_snapshot_at_all_is_null(self):
        report, _, _ = self.run_pipeline()
        self.assertIsNone(self.item(report, "github_trending", "NVIDIA/OpenShell")["metrics"]["stars_delta"])

    def test_R3_same_day_rerun_compares_with_earlier(self):
        stars = self.current_stars("NVIDIA/OpenShell")
        self.write_snap("2026-09-28", {"github": {"NVIDIA/OpenShell": stars - 500}})
        self.write_snap("2026-09-30", {"github": {"NVIDIA/OpenShell": stars - 1}})
        self.write_snap("2026-10-01", {"github": {"NVIDIA/OpenShell": 1}})
        report, _, _ = self.run_pipeline()
        self.assertEqual(self.item(report, "github_trending", "NVIDIA/OpenShell")["metrics"]["stars_delta"], 500)
        snap = json.loads((self.out / "snapshots" / "2026-09-30.json").read_text(encoding="utf-8"))
        self.assertEqual(snap["github"]["NVIDIA/OpenShell"], stars)


class TestR4Dedupe(Base):
    def test_R4_normalize_url(self):
        self.assertEqual(normalize_url("http://www.GitHub.com/NVIDIA/OpenShell/?utm_source=hn&x=1#top"),
                         "https://github.com/NVIDIA/OpenShell?x=1")

    def test_R4_hn_links_trending_repo(self):
        report, _, _ = self.run_pipeline()
        matches = [i for i in report["items"] if normalize_url(i["url"]) == "https://github.com/NVIDIA/OpenShell"]
        self.assertEqual(len(matches), 1)
        item = matches[0]
        self.assertEqual(item["source"], "github_trending")
        hn_refs = [a for a in item["also_in"] if a["source"] == "hn"]
        self.assertEqual(hn_refs, [{"source": "hn", "id": "49900003", "metrics": {"points": 88, "comments": 20}}])


class TestR5FailureIsolation(Base):
    def test_R5_one_source_down(self):
        self.fake.fail = ("github.com/trending",)
        report, path, code = self.run_pipeline()
        self.assertEqual(code, 0)
        self.assertEqual(report["sources"]["github_trending"]["status"], "error")
        self.assertIn("503", report["sources"]["github_trending"]["error"])
        self.assertEqual(report["sources"]["hn"]["status"], "ok")
        self.assertTrue(any(i["source"] == "hn" for i in report["items"]))
        self.assertTrue(path.exists())

    def test_R5_all_sources_down(self):
        self.fake.fail = ("http",)
        report, path, code = self.run_pipeline()
        self.assertEqual(code, 1)
        self.assertTrue(path.exists())
        self.assertTrue(all(s["status"] == "error" for s in report["sources"].values()))

    def test_R5_token_masked(self):
        token = "ghp_SECRET123"

        def leaky(cfg, c):
            raise http.FetchError(f"HTTP 401 with Authorization: Bearer {token}")

        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": token}), \
                mock.patch.dict(pipeline.SOURCES, {"github_search": leaky}):
            report, path, _ = self.run_pipeline()
        self.assertNotIn(token, path.read_text(encoding="utf-8"))
        self.assertIn("***", report["sources"]["github_search"]["error"])

    def test_R5_unrequested_gzip_body_is_decoded(self):
        import gzip
        self.assertEqual(http.decode_body(gzip.compress(RSS_XML.encode())), RSS_XML)
        self.assertEqual(http.decode_body(b"plain"), "plain")

    def test_R5_partial_rss_failure_is_warning(self):
        self.fake.fail = ("atom",)
        report, _, _ = self.run_pipeline()
        self.assertEqual(report["sources"]["rss"]["status"], "ok")
        self.assertTrue(any("Atom" in w for w in report["warnings"]))


class TestR6Output(Base):
    def run_cli(self, argv, now):
        cfg_path = self.out / "sources.toml"
        cfg_path.write_text((ROOT / "sources.toml").read_text(encoding="utf-8"), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(["fetch", "--config", str(cfg_path), "--out", str(self.out / "data")] + argv, now_utc=now)
        return code, buf.getvalue()

    def test_R6_default_date_is_taipei(self):
        code, _ = self.run_cli([], datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(code, 0)
        self.assertTrue((self.out / "data" / "raw" / "2026-10-01.json").exists())

    def test_R6_explicit_date_and_file_shape(self):
        code, _ = self.run_cli(["--date", "2026-09-30"], NOW)
        self.assertEqual(code, 0)
        data = json.loads((self.out / "data" / "raw" / "2026-09-30.json").read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"date", "fetched_at", "sources", "warnings", "items"})
        self.assertEqual(data["fetched_at"], "2026-09-30T01:00:00Z")
        for s in data["sources"].values():
            self.assertEqual(set(s), {"status", "count", "error"})

    def test_R6_summary_printed(self):
        self.fake.fail = ("openai.com", "deepmind", "blog.google", "huggingface.co/blog", "langchain",
                          "github.blog", "simonwillison", "techcrunch", "theverge")
        code, out = self.run_cli(["--date", "2026-09-30"], NOW)
        self.assertEqual(code, 0)
        self.assertRegex(out, r"hn\s+ok\s+\d+")
        self.assertRegex(out, r"rss\s+error\s+FetchError")

    def test_R6_rerun_overwrites(self):
        self.run_cli(["--date", "2026-09-30"], NOW)
        path = self.out / "data" / "raw" / "2026-09-30.json"
        path.write_text("stale", encoding="utf-8")
        self.run_cli(["--date", "2026-09-30"], NOW)
        self.assertNotEqual(path.read_text(encoding="utf-8"), "stale")


class TestD1Offline(Base):
    def test_D1_full_run_without_network(self):
        # urlopen 已被替換成會丟例外的替身；完整流程仍能跑完，證明沒有真的連網
        report, _, code = self.run_pipeline()
        self.assertEqual(code, 0)
        self.assertTrue(self.fake.urls)

    def test_D1_test_file_registered(self):
        cfg = json.loads((ROOT / "workflow.config.json").read_text(encoding="utf-8"))
        self.assertIn("tests/test_fetch.py", cfg["testFiles"])


if __name__ == "__main__":
    unittest.main()
