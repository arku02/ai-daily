"""Telegram Bot API 呼叫。token 不會出現在任何輸出（R5）。"""

import json
import urllib.error
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"


class TelegramError(Exception):
    pass


def _http_post(url, payload, timeout):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, f"{type(e).__name__}: {e}"


class Bot:
    def __init__(self, token, chat_id, post=_http_post, timeout=30):
        self.token = token
        self.chat_id = str(chat_id)
        self.post = post
        self.timeout = timeout

    def mask(self, text):
        text = str(text)
        return text.replace(self.token, "***") if self.token else text

    def call(self, method, payload):
        status, body = self.post(API.format(token=self.token, method=method), payload, self.timeout)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}
        if status == 200 and data.get("ok"):
            return data.get("result")
        hint = "（請先在 Telegram 對你的 bot 按 Start）" if status == 403 else ""
        desc = data.get("description") or body[:200]
        raise TelegramError(self.mask(f"Telegram {method} 失敗：HTTP {status} {desc}{hint}"))
