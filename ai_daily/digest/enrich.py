"""R3：替入選項目抓補充內容；失敗就略過。"""

import html
import re

from .. import http


def _strip_html(text):
    text = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _strip_markdown(text):
    text = re.sub(r"(?s)<[^>]+>", " ", text)                # README 裡的 HTML 標籤
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)        # 圖片、徽章
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)    # 連結留文字
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def _github_repo(url):
    m = re.match(r"https?://(?:www\.)?github\.com/([^/\s]+/[^/\s#?]+)/?$", url or "")
    return m.group(1) if m else None


def source_text(item):
    source = item["source"]
    if source == "hf_papers":
        return item.get("summary", "")
    if source.startswith("github"):
        return _strip_markdown(http.get_text(f"https://raw.githubusercontent.com/{item['id']}/HEAD/README.md"))
    if source == "hf_models":
        return _strip_markdown(http.get_text(f"https://huggingface.co/{item['id']}/raw/main/README.md"))
    repo = _github_repo(item.get("url"))
    if repo:
        return _strip_markdown(http.get_text(f"https://raw.githubusercontent.com/{repo}/HEAD/README.md"))
    return _strip_html(http.get_text(item["url"]))


def enrich(item, max_chars=3000):
    """回傳 (補充文字, 是否成功)。失敗時退回原始摘要。"""
    try:
        text = source_text(item)
    except (http.FetchError, ValueError, UnicodeError):
        return item.get("summary", "")[:max_chars], False
    if not text.strip():
        return item.get("summary", "")[:max_chars], False
    return text[:max_chars], True
