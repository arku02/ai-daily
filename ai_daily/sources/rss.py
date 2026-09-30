import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .. import http
from ..model import Item, iso_utc

ATOM = "{http://www.w3.org/2005/Atom}"


def _text(el, tag):
    found = el.find(tag)
    return (found.text or "").strip() if found is not None and found.text else ""


def _date(value):
    if not value:
        return None
    try:
        return iso_utc(parsedate_to_datetime(value).isoformat())
    except (TypeError, ValueError):
        return iso_utc(value)


def _clean(text, limit=600):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def parse_feed(xml_text, feed_name):
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):  # RSS 2.0
        link = _text(it, "link")
        items.append(Item(
            source="rss", id=link, title=_text(it, "title"), url=link,
            summary=_clean(_text(it, "description")),
            published_at=_date(_text(it, "pubDate")),
            extra={"feed": feed_name},
        ))
    for it in root.iter(f"{ATOM}entry"):  # Atom
        link_el = it.find(f"{ATOM}link[@rel='alternate']")
        if link_el is None:
            link_el = it.find(f"{ATOM}link")
        link = link_el.get("href", "") if link_el is not None else ""
        items.append(Item(
            source="rss", id=link, title=_text(it, f"{ATOM}title"), url=link,
            summary=_clean(_text(it, f"{ATOM}summary") or _text(it, f"{ATOM}content")),
            published_at=_date(_text(it, f"{ATOM}published") or _text(it, f"{ATOM}updated")),
            extra={"feed": feed_name},
        ))
    return [i for i in items if i.url]


def fetch(cfg, ctx):
    cutoff = ctx.now - timedelta(hours=int(cfg.get("window_hours", 36)))
    seen = {}
    errors = []
    feeds = cfg.get("feeds", [])
    for feed in feeds:
        try:
            parsed = parse_feed(http.get_text(feed["url"]), feed.get("name", feed["url"]))
        except (http.FetchError, ET.ParseError) as e:
            errors.append(f"{feed.get('name', feed['url'])}: {http.mask(e)}")
            continue
        for item in parsed:
            if not item.published_at:
                continue
            ts = datetime.strptime(item.published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                seen.setdefault(item.id, item)
    if feeds and len(errors) == len(feeds):
        raise http.FetchError("; ".join(errors))
    ctx.warnings.extend(f"rss {e}" for e in errors)
    return sorted(seen.values(), key=lambda i: i.published_at, reverse=True)
