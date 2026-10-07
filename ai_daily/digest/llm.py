"""R5：Gemini 客戶端。只用標準函式庫；key 從環境變數或 .env 讀取。"""

import json
import re
import time
import urllib.error
import urllib.request

from .. import env

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(Exception):
    pass


class BadResponse(LLMError):
    """模型有回應，但不是可解析的 JSON。"""


def load_key(root="."):
    return env.get("GEMINI_API_KEY", root)


def parse_json_text(text):
    text = (text or "").strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        try:
            # 模型偶爾在完整的 JSON 後面多吐一段（Extra data）：保留前面完整的部分
            return json.JSONDecoder().raw_decode(text)[0]
        except json.JSONDecodeError:
            raise BadResponse(f"模型回應不是 JSON：{e}") from None


def _http_post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, f"{type(e).__name__}: {e}"


class Gemini:
    def __init__(self, key, models, temperature=0.4, timeout=180, post=_http_post,
                 retry_waits=(20, 60), sleep=time.sleep):
        if not models:
            raise ValueError("models 不能是空的")
        self.key = key
        self.models = list(models)
        self.temperature = temperature
        self.timeout = timeout
        self.post = post
        self.retry_waits = list(retry_waits)
        self.sleep = sleep
        self.calls = 0
        self.models_used = []
        self.log = []  # 每次成功回應的原始文字，供事後查原因

    def mask(self, text):
        text = str(text)
        return text.replace(self.key, "***") if self.key else text

    def generate_json(self, prompt):
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": self.temperature},
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.key}
        errors = []
        retired = set()  # 回應 404 的模型（例如已停止提供），之後的輪次不再嘗試
        for round_no, wait in enumerate([0] + self.retry_waits):
            candidates = [m for m in self.models if m not in retired]
            if not candidates:
                break
            if wait:
                self.sleep(wait)
            for model in candidates:
                self.calls += 1
                status, text = self.post(API.format(model=model), body, headers, self.timeout)
                if status == 200:
                    try:
                        data = json.loads(text)
                        parts = data["candidates"][0]["content"]["parts"]
                        out = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        raise BadResponse(self.mask(f"{model} 回應格式異常：{text[:200]}")) from None
                    if model not in self.models_used:
                        self.models_used.append(model)
                    self.log.append({"model": model, "prompt": prompt.split("\n", 1)[0], "response": out})
                    return parse_json_text(out)
                errors.append(f"[第 {round_no + 1} 輪] {model}: HTTP {status} {text[:160]}")
                if status == 404:
                    retired.add(model)
                elif not (status == 429 or status >= 500 or status == 0):
                    # 400、401、403 等換模型或重試都沒用
                    raise LLMError(self.mask("模型呼叫失敗：" + " | ".join(errors)))
        raise LLMError(self.mask("所有模型都失敗：" + " | ".join(errors)))
