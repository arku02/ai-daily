"""R1：從原始資料挑出候選，編上短代號，做成給 LLM 的精簡清單。"""

import re
from dataclasses import dataclass

# 編號順序即規格 R1 列出的來源順序
ORDER = ["hn", "github_trending", "github_search", "hf_models", "hf_papers", "rss"]


def _first(*values):
    for v in values:
        if v is not None:
            return v
    return 0


SORT_KEYS = {
    "hn": lambda i: i["metrics"].get("points") or 0,
    "github_trending": lambda i: i["metrics"].get("stars_today") or 0,
    "github_search": lambda i: _first(i["metrics"].get("stars_delta"), i["metrics"].get("stars")),
    "hf_models": lambda i: _first(i["metrics"].get("likes_delta"), i["metrics"].get("likes")),
    "hf_papers": lambda i: i["metrics"].get("upvotes") or 0,
    "rss": lambda i: i.get("published_at") or "",
}


@dataclass
class Candidate:
    ref: str
    item: dict


def pick(raw, caps):
    by_source = {s: [] for s in ORDER}
    for item in raw["items"]:
        if item["source"] in by_source:
            by_source[item["source"]].append(item)
    picked = []
    for source in ORDER:
        items = sorted(by_source[source], key=SORT_KEYS[source], reverse=True)
        picked.extend(items[: int(caps.get(source, 20))])
    return [Candidate(f"c{n}", item) for n, item in enumerate(picked, 1)]


def _metrics_text(item):
    parts = [f"{k}={v}" for k, v in item["metrics"].items() if v is not None]
    for other in item.get("also_in", []):
        if other["source"] == "hn" and other["metrics"].get("points") is not None:
            parts.append(f"hn_points={other['metrics']['points']}")
    return " ".join(parts)


def _hint(item):
    extra = item.get("extra", {})
    for key in ("feed", "language", "pipeline_tag", "organization"):
        if extra.get(key):
            return str(extra[key])
    return ""


def _short(text, limit):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def compact_lines(candidates, summary_chars=220):
    """每個候選一行；刻意不放網址（R1），連結之後由程式帶入。"""
    lines = []
    for c in candidates:
        it = c.item
        fields = [c.ref, it["source"], _short(it["title"], 140)]
        hint = _hint(it)
        if hint:
            fields.append(hint)
        metrics = _metrics_text(it)
        if metrics:
            fields.append(metrics)
        summary = _short(it.get("summary"), summary_chars)
        if summary:
            fields.append(summary)
        lines.append(" | ".join(fields))
    return lines
