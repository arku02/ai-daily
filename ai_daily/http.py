"""所有對外 HTTP 請求都經過這裡，測試時整個替換掉。"""

import gzip
import json
import os
import urllib.error
import urllib.request

USER_AGENT = "ai-daily/0.1 (+https://github.com/arku02/ai-daily)"
TIMEOUT = 20
RETRIES = 1


class FetchError(Exception):
    pass


def _token():
    return os.environ.get("GITHUB_TOKEN") or ""


def mask(text):
    """把 GitHub token 從任何文字中遮蔽掉。"""
    token = _token()
    text = str(text)
    if token:
        text = text.replace(token, "***")
    return text


def decode_body(body):
    # 有些伺服器（例如 deepmind.google）即使沒要求也會間歇回傳 gzip
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return body.decode("utf-8", errors="replace")


def get_text(url):
    headers = {"User-Agent": USER_AGENT}
    if url.startswith("https://api.github.com/"):
        headers["Accept"] = "application/vnd.github+json"
        if _token():
            headers["Authorization"] = f"Bearer {_token()}"
    last = None
    for _ in range(RETRIES + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return decode_body(resp.read())
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {url}"
            if e.code < 500 and e.code != 429:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"{type(e).__name__}: {e} ({url})"
    raise FetchError(mask(last))


def get_json(url):
    text = get_text(url)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise FetchError(f"invalid JSON from {url}: {e}") from None
