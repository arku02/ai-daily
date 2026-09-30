from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass
class Item:
    source: str
    id: str
    title: str
    url: str
    summary: str = ""
    published_at: str | None = None
    metrics: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)
    also_in: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def iso_utc(value):
    """把 epoch 秒數或 ISO 字串轉成 UTC ISO 8601；無法解析時回傳 None。"""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError):
        return None


def normalize_url(url):
    if not url:
        return ""
    parts = urlsplit(url.strip())
    scheme = "https" if parts.scheme in ("http", "https", "") else parts.scheme
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not k.lower().startswith("utm_")])
    return urlunsplit((scheme, host, path, query, ""))
