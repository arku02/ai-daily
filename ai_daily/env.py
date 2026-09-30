"""讀取機密設定：先看環境變數，沒有再讀專案根目錄的 .env。"""

import os
import re
from pathlib import Path


def get(name, root="."):
    value = os.environ.get(name, "").strip()
    if value:
        return value
    env = Path(root) / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            m = re.match(rf"\s*{re.escape(name)}\s*=\s*(.*)$", line)
            if m:
                return m.group(1).strip().strip("'\"")
    return ""
