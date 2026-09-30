from urllib.parse import urlencode

from .. import http
from ..model import Item, iso_utc

API = "https://hn.algolia.com/api/v1/search"


def discussion_url(story_id):
    return f"https://news.ycombinator.com/item?id={story_id}"


def to_item(hit):
    sid = str(hit["objectID"])
    return Item(
        source="hn",
        id=sid,
        title=hit.get("title") or "",
        url=hit.get("url") or discussion_url(sid),
        published_at=iso_utc(hit.get("created_at_i")),
        metrics={"points": hit.get("points"), "comments": hit.get("num_comments")},
        extra={"discussion": discussion_url(sid)},
    )


def fetch(cfg, ctx):
    since = int(ctx.now.timestamp()) - int(cfg.get("window_hours", 36)) * 3600
    min_points = int(cfg.get("min_points", 30))
    seen = {}
    for kw in cfg.get("keywords", []):
        query = urlencode({
            "query": kw,
            "tags": "story",
            "numericFilters": f"created_at_i>{since},points>={min_points}",
            "hitsPerPage": int(cfg.get("per_keyword", 30)),
        })
        data = http.get_json(f"{API}?{query}")
        for hit in data.get("hits", []):
            if (hit.get("points") or 0) < min_points:
                continue
            item = to_item(hit)
            seen.setdefault(item.id, item)
    return sorted(seen.values(), key=lambda i: -(i.metrics["points"] or 0))
