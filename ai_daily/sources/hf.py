from datetime import timedelta

from .. import http
from ..model import Item, iso_utc

MODELS_API = "https://huggingface.co/api/models"
PAPERS_API = "https://huggingface.co/api/daily_papers"


def model_to_item(m):
    mid = m.get("id") or m.get("modelId")
    return Item(
        source="hf_models",
        id=mid,
        title=mid,
        url=f"https://huggingface.co/{mid}",
        published_at=iso_utc(m.get("createdAt")),
        metrics={
            "likes": m.get("likes"),
            "downloads": m.get("downloads"),
            "trending_score": m.get("trendingScore"),
        },
        extra={"pipeline_tag": m.get("pipeline_tag"), "library": m.get("library_name")},
    )


def fetch_models(cfg, ctx):
    limit = int(cfg.get("limit", 50))
    allowed = set(cfg.get("pipelines", []))
    data = http.get_json(f"{MODELS_API}?sort=trendingScore&limit={limit}")
    return [model_to_item(m) for m in data
            if not allowed or m.get("pipeline_tag") in allowed]


def paper_to_item(entry):
    p = entry.get("paper", entry)
    pid = p["id"]
    org = entry.get("organization") or p.get("organization") or {}
    return Item(
        source="hf_papers",
        id=pid,
        title=p.get("title") or entry.get("title") or "",
        url=f"https://huggingface.co/papers/{pid}",
        summary=p.get("summary") or entry.get("summary") or "",
        published_at=iso_utc(p.get("publishedAt") or entry.get("publishedAt")),
        metrics={"upvotes": p.get("upvotes"), "github_stars": p.get("githubStars")},
        extra={
            "arxiv": f"https://arxiv.org/abs/{pid}",
            "github": p.get("githubRepo"),
            "organization": org.get("fullname") or org.get("name"),
        },
    )


def fetch_papers(cfg, ctx):
    day = ctx.date - timedelta(days=int(cfg.get("days_back", 1)))
    min_upvotes = int(cfg.get("min_upvotes", 0))
    data = http.get_json(f"{PAPERS_API}?date={day.isoformat()}")
    items = [paper_to_item(e) for e in data]
    items = [i for i in items if (i.metrics["upvotes"] or 0) >= min_upvotes]
    return sorted(items, key=lambda i: -(i.metrics["upvotes"] or 0))
