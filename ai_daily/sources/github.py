import html
import re
from datetime import timedelta
from urllib.parse import quote

from .. import http
from ..model import Item, iso_utc

SEARCH_API = "https://api.github.com/search/repositories"

_ARTICLE = re.compile(r'<article class="Box-row">(.*?)</article>', re.S)
_NAME = re.compile(r'<h2[^>]*>\s*<a[^>]*href="/([^"/]+/[^"/]+)"', re.S)
_DESC = re.compile(r'<p class="col-9[^"]*">(.*?)</p>', re.S)
_LANG = re.compile(r'itemprop="programmingLanguage">([^<]+)<')
_TOTAL = re.compile(r'href="/[^"/]+/[^"/]+/stargazers"[^>]*>(?:\s|<svg.*?</svg>)*([\d,]+)\s*</a>', re.S)
_PERIOD = re.compile(r'([\d,]+)\s+stars\s+(?:today|this week|this month)')


def _num(text):
    return int(text.replace(",", "")) if text else None


def parse_trending(page):
    items = []
    for block in _ARTICLE.findall(page):
        name = _NAME.search(block)
        if not name:
            continue
        repo = name.group(1)
        desc = _DESC.search(block)
        lang = _LANG.search(block)
        total = _TOTAL.search(block)
        period = _PERIOD.search(block)
        items.append(Item(
            source="github_trending",
            id=repo,
            title=repo,
            url=f"https://github.com/{repo}",
            summary=html.unescape(re.sub(r"<[^>]+>", "", desc.group(1))).strip() if desc else "",
            metrics={
                "stars": _num(total.group(1)) if total else None,
                "stars_today": _num(period.group(1)) if period else None,
            },
            extra={"language": lang.group(1).strip() if lang else None},
        ))
    return items


def fetch_trending(cfg, ctx):
    seen = {}
    for url in cfg.get("urls", ["https://github.com/trending?since=daily"]):
        page = http.get_text(url)
        parsed = parse_trending(page)
        if not parsed:
            raise http.FetchError(f"no repositories parsed from {url} (page layout changed?)")
        for item in parsed:
            seen.setdefault(item.id, item)
    return sorted(seen.values(), key=lambda i: -(i.metrics["stars_today"] or 0))


def repo_to_item(r):
    return Item(
        source="github_search",
        id=r["full_name"],
        title=r["full_name"],
        url=r.get("html_url") or f"https://github.com/{r['full_name']}",
        summary=r.get("description") or "",
        published_at=iso_utc(r.get("created_at")),
        metrics={"stars": r.get("stargazers_count"), "forks": r.get("forks_count")},
        extra={
            "language": r.get("language"),
            "license": (r.get("license") or {}).get("spdx_id"),
            "topics": r.get("topics") or [],
        },
    )


def fetch_search(cfg, ctx):
    since = (ctx.date - timedelta(days=int(cfg.get("created_within_days", 14)))).isoformat()
    per_page = int(cfg.get("per_page", 30))
    seen = {}
    for q in cfg.get("queries", []):
        url = (f"{SEARCH_API}?q={quote(q)}+created:>{since}"
               f"&sort=stars&order=desc&per_page={per_page}")
        data = http.get_json(url)
        for r in data.get("items", []):
            item = repo_to_item(r)
            seen.setdefault(item.id, item)
    return sorted(seen.values(), key=lambda i: -(i.metrics["stars"] or 0))
