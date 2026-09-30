import json
import os
import shutil
import tempfile
import unittest
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

from ai_daily import cli, http
from ai_daily.digest import candidates as cand
from ai_daily.digest import enrich, llm, select, write
from ai_daily.digest.llm import BadResponse, Gemini, LLMError

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 30, 1, 0, tzinfo=timezone.utc)
DAY = date(2026, 9, 30)


def item(source, iid, title, url, metrics, summary="", extra=None, also_in=None, published_at=None):
    return {"source": source, "id": iid, "title": title, "url": url, "summary": summary,
            "published_at": published_at, "metrics": metrics, "extra": extra or {}, "also_in": also_in or []}


def raw_data():
    items = [
        item("github_trending", "NVIDIA/OpenShell", "NVIDIA/OpenShell", "https://github.com/NVIDIA/OpenShell",
             {"stars": 11049, "stars_today": 990, "stars_delta": None}, "safe runtime for agents",
             {"language": "Rust"},
             [{"source": "hn", "id": "49900003", "metrics": {"points": 88, "comments": 20}}]),
        item("github_trending", "vectorize-io/hindsight", "vectorize-io/hindsight",
             "https://github.com/vectorize-io/hindsight", {"stars": 43362, "stars_today": 2575, "stars_delta": None},
             "Agent memory that learns", {"language": "Python"}),
        item("hn", "49896604", "Dots: Always-on agents", "https://openai.com/index/introducing-dots/",
             {"points": 608, "comments": 472}, "", {"discussion": "https://news.ycombinator.com/item?id=49896604"}),
        item("hn", "49900001", "Ask HN: testing agents", "https://news.ycombinator.com/item?id=49900001",
             {"points": 45, "comments": 60}, "", {"discussion": "https://news.ycombinator.com/item?id=49900001"}),
        item("hn", "49900009", "Small story", "https://example.com/small", {"points": 31, "comments": 2}, "",
             {"discussion": "https://news.ycombinator.com/item?id=49900009"}),
        item("hf_papers", "2609.33295", "TraceDance", "https://huggingface.co/papers/2609.33295",
             {"upvotes": 60, "github_stars": None}, "Build agent benchmarks from traces.",
             {"arxiv": "https://arxiv.org/abs/2609.33295", "github": "https://github.com/ZhishanQ/TraceDance"}),
        item("hf_models", "deepseek-ai/DeepSeek-V4.1-Flash", "deepseek-ai/DeepSeek-V4.1-Flash",
             "https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash", {"likes": 3909, "likes_delta": None}),
        item("rss", "https://simonwillison.net/x", "Sonnet 5.5", "https://simonwillison.net/x",
             {}, "Anthropic released Sonnet 5.5", {"feed": "Simon Willison"}, published_at="2026-09-29T10:00:00Z"),
    ]
    return {"date": "2026-09-30", "items": items}


class FakeLLM:
    """依序回傳預先準備的回應；回應可以是例外。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
        self.calls = 0
        self.models_used = ["fake-model"]

    def generate_json(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        r = self.responses.pop(0) if self.responses else {}
        if isinstance(r, Exception):
            raise r
        return r

    def mask(self, t):
        return str(t)


def deep(ref, title="標題"):
    return {"ref": ref, "title": title, "tags": ["標籤"], "summary": "摘要內容", "key_points": ["重點"],
            "how_to_use": "用法", "url": "https://fake.example.com"}


def brief(ref):
    return {"ref": ref, "title": "短標題", "one_liner": "一句話"}


def no_network(*a, **k):
    raise AssertionError("network access in tests")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ("digest.toml", "profile.example.toml"):
            shutil.copy(ROOT / name, self.root / name)
        (self.root / "data" / "raw").mkdir(parents=True)
        (self.root / "data" / "raw" / "2026-09-30.json").write_text(json.dumps(raw_data()), encoding="utf-8")
        self.fetched = []

        def fake_get_text(url):
            self.fetched.append(url)
            if "openai.com" in url:
                raise http.FetchError("HTTP 403 " + url)
            return "README text for " + url

        for p in (mock.patch.object(http, "get_text", side_effect=fake_get_text),
                  mock.patch.object(urllib.request, "urlopen", side_effect=no_network),
                  mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""})):
            p.start()
            self.addCleanup(p.stop)
        self.cands = cand.pick(raw_data(), {"hn": 25, "github_trending": 25, "github_search": 30,
                                            "hf_models": 20, "hf_papers": 25, "rss": 50})
        self.refs = {c.item["id"]: c.ref for c in self.cands}

    def run_cli(self, args, llm_obj=None):
        lines = []
        with mock.patch("builtins.print", side_effect=lambda *a, **k: lines.append(" ".join(map(str, a)))):
            code = cli.main(["digest", "--root", str(self.root)] + args, now_utc=NOW,
                            make_llm=(lambda cfg: llm_obj) if llm_obj else None)
        return code, "\n".join(lines)

    def selection(self):
        r = self.refs
        return {
            "tldr": ["一", "二", "三"],
            "sections": {
                "news": {"items": [r["49896604"]], "brief": [r["49900001"]]},
                "models": {"items": [r["deepseek-ai/DeepSeek-V4.1-Flash"]], "brief": []},
                "arch": {"items": [r["2609.33295"]], "brief": []},
                "github": {"items": [r["vectorize-io/hindsight"], r["NVIDIA/OpenShell"]], "brief": []},
            },
            "try_one": r["vectorize-io/hindsight"],
        }


class TestR1Candidates(Base):
    def test_R1_per_source_cap_and_order(self):
        cs = cand.pick(raw_data(), {"hn": 2})
        hn_ids = [c.item["id"] for c in cs if c.item["source"] == "hn"]
        self.assertEqual(hn_ids, ["49896604", "49900001"])
        self.assertEqual(cs[0].ref, "c1")
        self.assertEqual(cs[0].item["source"], "hn")  # 依 R1 來源順序編號

    def test_R1_trending_sorted_by_stars_today(self):
        ids = [c.item["id"] for c in self.cands if c.item["source"] == "github_trending"]
        self.assertEqual(ids, ["vectorize-io/hindsight", "NVIDIA/OpenShell"])

    def test_R1_compact_lines_have_no_urls(self):
        lines = cand.compact_lines(self.cands)
        self.assertEqual(len(lines), len(self.cands))
        self.assertFalse(any("http" in l for l in lines))
        self.assertTrue(any("hn_points=88" in l for l in lines))

    def test_R1_missing_raw_file(self):
        fake = FakeLLM([])
        code, out = self.run_cli(["--date", "2026-10-01"], fake)
        self.assertEqual(code, 2)
        self.assertIn("fetch", out)
        self.assertEqual(fake.calls, 0)


class TestR2Selection(Base):
    caps = {n: {"items": 5, "brief": 3} for n in select.SECTIONS}

    def test_R2_invalid_selections_dropped(self):
        v = select.validate({"sections": {"news": {"items": ["c3", "c999", "c3"]}, "gossip": {"items": ["c1"]}},
                             "try_one": "c999"}, {"c1", "c3"}, self.caps)
        self.assertEqual(v["sections"]["news"]["items"], ["c3"])
        self.assertNotIn("gossip", v["sections"])
        self.assertEqual(v["try_one"], [])

    def test_R2_try_one_ranked_candidates(self):
        v = select.validate({"try_one": ["c2", "c999", "c2", "c1", "c3", "c4"]}, {"c1", "c2", "c3", "c4"}, self.caps)
        self.assertEqual(v["try_one"], ["c2", "c1", "c3"])

    def test_R2_section_cap(self):
        refs = [f"c{i}" for i in range(1, 8)]
        v = select.validate({"sections": {"news": {"items": refs}}}, set(refs), self.caps)
        self.assertEqual(v["sections"]["news"]["items"], refs[:5])

    def test_R2_ref_used_once_across_sections(self):
        v = select.validate({"sections": {"news": {"items": ["c1"]}, "github": {"items": ["c1", "c2"]}}},
                            {"c1", "c2"}, self.caps)
        self.assertEqual(v["sections"]["github"]["items"], ["c2"])

    def test_R2_exclusions_in_prompt(self):
        profile = {"exclude_topics": ["融資新聞", "公司人事"], "try_one_rules": ["15 分鐘內看到結果"]}
        p = select.build_prompt(["c1 | hn | x"], profile, self.caps, "2026-09-30")
        self.assertIn("融資新聞", p)
        self.assertIn("公司人事", p)
        self.assertIn("15 分鐘內看到結果", p)


class TestR3Enrichment(Base):
    def test_R3_github_readme_and_model_card(self):
        by_id = {c.item["id"]: c.item for c in self.cands}
        text, ok = enrich.enrich(by_id["NVIDIA/OpenShell"])
        self.assertTrue(ok)
        self.assertIn("raw.githubusercontent.com/NVIDIA/OpenShell/HEAD/README.md", self.fetched[-1])
        enrich.enrich(by_id["deepseek-ai/DeepSeek-V4.1-Flash"])
        self.assertIn("huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/raw/main/README.md", self.fetched[-1])

    def test_R3_paper_uses_abstract_without_request(self):
        by_id = {c.item["id"]: c.item for c in self.cands}
        before = len(self.fetched)
        text, ok = enrich.enrich(by_id["2609.33295"])
        self.assertEqual(text, "Build agent benchmarks from traces.")
        self.assertEqual(len(self.fetched), before)

    def test_R3_enrichment_failure(self):
        by_id = {c.item["id"]: c.item for c in self.cands}
        text, ok = enrich.enrich(by_id["49896604"])  # openai.com → 403
        self.assertFalse(ok)
        self.assertEqual(text, "")

    def test_R3_truncated(self):
        by_id = {c.item["id"]: c.item for c in self.cands}
        text, _ = enrich.enrich(by_id["NVIDIA/OpenShell"], max_chars=10)
        self.assertEqual(len(text), 10)


class TestR4Writing(Base):
    def cands_for(self, *ids):
        by_id = {c.item["id"]: c for c in self.cands}
        return [by_id[i] for i in ids]

    def test_R4_sources_come_from_raw_data(self):
        c = self.cands_for("NVIDIA/OpenShell")
        fake = FakeLLM([{"items": [deep(c[0].ref)], "brief": []}])
        items, _ = write.write_section(fake, "github", c, [], {}, {}, "2026-09-30", [])
        dumped = json.dumps(items)
        self.assertNotIn("fake.example.com", dumped)
        self.assertEqual(items[0]["sources"], [
            {"label": "GitHub", "url": "https://github.com/NVIDIA/OpenShell"},
            {"label": "HN 討論（88 分）", "url": "https://news.ycombinator.com/item?id=49900003"},
        ])

    def test_R4_paper_and_hn_sources(self):
        paper, story = self.cands_for("2609.33295", "49896604")
        labels = [s["label"] for s in write.sources_for(paper.item)]
        self.assertEqual(labels, ["HF Papers", "arXiv", "GitHub"])
        self.assertEqual([s["label"] for s in write.sources_for(story.item)], ["原文", "HN 討論（608 分）"])

    def test_R4_fallback_item(self):
        a, b = self.cands_for("vectorize-io/hindsight", "NVIDIA/OpenShell")
        bad_b = {**deep(b.ref), "summary": ""}
        fake = FakeLLM([{"items": [deep(a.ref), bad_b]}, {"items": [bad_b]}])
        warnings = []
        items, _ = write.write_section(fake, "github", [a, b], [], {}, {}, "2026-09-30", warnings)
        self.assertEqual(fake.calls, 2)  # 整批重試一次
        self.assertFalse(items[0]["fallback"])
        self.assertEqual(items[0]["summary"], "摘要內容")
        self.assertTrue(items[1]["fallback"])
        self.assertEqual(items[1]["title"], "NVIDIA/OpenShell")
        self.assertEqual(items[1]["summary"], "safe runtime for agents")
        self.assertTrue(any(b.ref in w for w in warnings))

    def test_R4_retry_fixes_batch(self):
        a = self.cands_for("vectorize-io/hindsight")[0]
        fake = FakeLLM([BadResponse("not json"), {"items": [deep(a.ref)]}])
        items, _ = write.write_section(fake, "github", [a], [], {}, {}, "2026-09-30", [])
        self.assertFalse(items[0]["fallback"])

    def test_R4_try_one_steps_limited(self):
        a = self.cands_for("vectorize-io/hindsight")[0]
        fake = FakeLLM([{"title": "試 hindsight", "why": "好用", "steps": ["1", "2", "3", "4"],
                         "success_check": "看到記憶"}])
        t = write.write_try_one(fake, a, "readme", {}, "2026-09-30", [])
        self.assertEqual(t["steps"], ["1", "2", "3"])
        self.assertEqual(t["sources"][0]["url"], "https://github.com/vectorize-io/hindsight")


    def test_R4_try_one_skipped_by_writer(self):
        a = self.cands_for("vectorize-io/hindsight")[0]
        for resp in (None, {"skip": True, "reason": "需要付費 key"}):
            warnings = []
            self.assertIsNone(write.write_try_one(FakeLLM([resp]), a, "readme", {}, "2026-09-30", warnings))
            self.assertTrue(any("跳過" in w for w in warnings))


class TestR5Client(Base):
    def post_seq(self, responses):
        calls = []

        def post(url, body, headers, timeout):
            calls.append(url)
            return responses.pop(0)
        return post, calls

    @staticmethod
    def ok(obj):
        return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}}]})

    def test_R5_missing_key(self):
        code, out = self.run_cli(["--date", "2026-09-30"])
        self.assertEqual(code, 2)
        self.assertIn(".env", out)

    def test_R5_key_from_env_file(self):
        (self.root / ".env").write_text("# c\nGEMINI_API_KEY='abc123'\n", encoding="utf-8")
        self.assertEqual(llm.load_key(self.root), "abc123")
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "fromenv"}):
            self.assertEqual(llm.load_key(self.root), "fromenv")

    def test_R5_quota_fallback(self):
        post, calls = self.post_seq([(429, "quota"), self.ok({"a": 1})])
        g = Gemini("k", ["m1", "m2"], post=post)
        self.assertEqual(g.generate_json("hi"), {"a": 1})
        self.assertEqual(g.models_used, ["m2"])
        self.assertEqual(g.calls, 2)
        self.assertIn("models/m1:", calls[0])

    def test_R5_all_models_fail(self):
        post, _ = self.post_seq([(429, "q"), (503, "down")])
        with self.assertRaises(LLMError):
            Gemini("k", ["m1", "m2"], post=post, retry_waits=[]).generate_json("hi")

    def test_R5_busy_then_retry(self):
        waits = []
        post, calls = self.post_seq([(503, "busy"), (503, "busy"), self.ok({"ok": 1})])
        g = Gemini("k", ["m1", "m2"], post=post, retry_waits=[20, 60], sleep=waits.append)
        self.assertEqual(g.generate_json("hi"), {"ok": 1})
        self.assertEqual(waits, [20])
        self.assertEqual(g.calls, 3)
        self.assertIn("models/m1:", calls[2])

    def test_R5_retired_model_not_retried(self):
        waits = []
        post, calls = self.post_seq([(503, "busy"), (404, "gone"), (503, "busy"), (503, "busy")])
        g = Gemini("k", ["m1", "m2"], post=post, retry_waits=[20, 60], sleep=waits.append)
        with self.assertRaises(LLMError) as ctx:
            g.generate_json("hi")
        self.assertEqual(waits, [20, 60])
        self.assertEqual([c.split("models/")[1].split(":")[0] for c in calls], ["m1", "m2", "m1", "m1"])
        self.assertIn("第 3 輪", str(ctx.exception))

    def test_R5_non_retryable_does_not_wait(self):
        waits = []
        post, calls = self.post_seq([(403, "forbidden")])
        with self.assertRaises(LLMError):
            Gemini("k", ["m1", "m2"], post=post, retry_waits=[20], sleep=waits.append).generate_json("hi")
        self.assertEqual(waits, [])
        self.assertEqual(len(calls), 1)

    def test_R5_model_list_has_no_retired_model(self):
        import tomllib
        cfg = tomllib.loads((ROOT / "digest.toml").read_text(encoding="utf-8"))["llm"]
        self.assertNotIn("gemini-2.5-flash", cfg["models"])
        self.assertEqual(cfg["retry_waits"], [20, 60])

    def test_R5_key_masked(self):
        key = "SECRETKEY123"
        post, _ = self.post_seq([(400, f"API key {key} not valid")])  # 400 不重試
        with self.assertRaises(LLMError) as ctx:
            Gemini(key, ["m1", "m2"], post=post).generate_json("hi")
        self.assertNotIn(key, str(ctx.exception))
        self.assertIn("***", str(ctx.exception))

    def test_R5_json_mode_and_fenced_text(self):
        seen = {}

        def post(url, body, headers, timeout):
            seen.update(body=body, headers=headers)
            return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": '```json\n{"x": 2}\n```'}]}}]})
        self.assertEqual(Gemini("k", ["m"], post=post).generate_json("hi"), {"x": 2})
        self.assertEqual(seen["body"]["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(seen["headers"]["x-goog-api-key"], "k")


class TestR6Output(Base):
    def test_R6_dry_run(self):
        code, out = self.run_cli(["--date", "2026-09-30", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("候選 8 筆", out)
        self.assertIn("字元", out)
        self.assertFalse((self.root / "data" / "digest").exists())

    def test_R6_output_shape(self):
        sel = self.selection()
        r = self.refs
        fake = FakeLLM([
            sel,
            {"items": [deep(r["49896604"])], "brief": [brief(r["49900001"])]},
            {"items": [deep(r["deepseek-ai/DeepSeek-V4.1-Flash"])]},
            {"items": [deep(r["2609.33295"])]},
            {"items": [deep(r["vectorize-io/hindsight"]), deep(r["NVIDIA/OpenShell"])]},
            {"title": "試 hindsight", "why": "好用", "steps": ["pip install"], "success_check": "ok"},
        ])
        code, out = self.run_cli(["--date", "2026-09-30"], fake)
        self.assertEqual(code, 0, out)
        d = json.loads((self.root / "data" / "digest" / "2026-09-30.json").read_text(encoding="utf-8"))
        self.assertEqual(set(d), {"date", "generated_at", "models_used", "llm_calls", "tldr", "sections",
                                  "try_one", "warnings"})
        self.assertEqual(d["llm_calls"], fake.calls)
        self.assertEqual(d["llm_calls"], 6)
        self.assertEqual(set(d["sections"]), {"news", "models", "arch", "github"})
        self.assertEqual(d["sections"]["news"]["brief"][0]["one_liner"], "一句話")
        self.assertEqual(d["try_one"]["title"], "試 hindsight")
        self.assertEqual(d["tldr"], ["一", "二", "三"])
        self.assertTrue(any("49896604" in w or r["49896604"] in w for w in d["warnings"]))  # openai 403

    def test_R4_try_one_falls_through_to_next_candidate(self):
        sel = self.selection()
        r = self.refs
        sel["try_one"] = [r["NVIDIA/OpenShell"], r["vectorize-io/hindsight"]]
        for s in sel["sections"].values():
            s["items"], s["brief"] = [], []
        fake = FakeLLM([sel, {"skip": True, "reason": "需要 Linux"},
                        {"title": "試 hindsight", "why": "好用", "steps": ["pip install"], "success_check": "ok"}])
        code, _ = self.run_cli(["--date", "2026-09-30"], fake)
        self.assertEqual(code, 0)
        d = json.loads((self.root / "data" / "digest" / "2026-09-30.json").read_text(encoding="utf-8"))
        self.assertEqual(d["try_one"]["id"], "vectorize-io/hindsight")
        self.assertTrue(any(r["NVIDIA/OpenShell"] in w and "跳過" in w for w in d["warnings"]))

    def test_R6_llm_failure_exit_1(self):
        fake = FakeLLM([LLMError("all models failed")])
        code, _ = self.run_cli(["--date", "2026-09-30"], fake)
        self.assertEqual(code, 1)
        self.assertFalse((self.root / "data" / "digest" / "2026-09-30.json").exists())


class TestR7Profile(Base):
    def test_R7_example_fallback(self):
        code, out = self.run_cli(["--date", "2026-09-30", "--dry-run"])
        self.assertIn("profile.example.toml", out)

    def test_R7_private_profile_used(self):
        (self.root / "profile.toml").write_text('background = "私人背景XYZ"\n', encoding="utf-8")
        fake = FakeLLM([{"sections": {}}])
        self.run_cli(["--date", "2026-09-30"], fake)
        self.assertIn("私人背景XYZ", fake.prompts[0])

    def test_R7_profile_gitignored(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("profile.toml", lines)


class TestD1Offline(Base):
    def test_D1_full_run_without_network(self):
        fake = FakeLLM([self.selection()])
        code, _ = self.run_cli(["--date", "2026-09-30"], fake)
        self.assertEqual(code, 0)  # 寫作回應是空的 → 全部降級，但仍完成

    def test_D1_test_file_registered(self):
        cfg = json.loads((ROOT / "workflow.config.json").read_text(encoding="utf-8"))
        self.assertIn("tests/test_digest.py", cfg["testFiles"])


if __name__ == "__main__":
    unittest.main()
