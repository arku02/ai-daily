"""每日快照：記錄 GitHub 星數與 HF 模型讚數，用來計算成長量（R3）。"""

import json
from pathlib import Path

GROWTH_FIELDS = {
    "github_trending": ("github", "stars", "stars_delta"),
    "github_search": ("github", "stars", "stars_delta"),
    "hf_models": ("hf_models", "likes", "likes_delta"),
}


def previous(snap_dir, date):
    """回傳日期早於 date 的最新快照；沒有則回傳空 dict。"""
    snap_dir = Path(snap_dir)
    if not snap_dir.is_dir():
        return {}
    earlier = sorted(p for p in snap_dir.glob("*.json") if p.stem < date.isoformat())
    if not earlier:
        return {}
    return json.loads(earlier[-1].read_text(encoding="utf-8"))


def apply_growth(items, prev):
    """在 items 的 metrics 加上成長量，並回傳今天的快照內容。"""
    today = {}
    for item in items:
        spec = GROWTH_FIELDS.get(item.source)
        if not spec:
            continue
        group, field, delta_field = spec
        value = item.metrics.get(field)
        old = prev.get(group, {}).get(item.id)
        item.metrics[delta_field] = value - old if value is not None and old is not None else None
        if value is not None:
            today.setdefault(group, {})[item.id] = value
    return today


def save(snap_dir, date, data):
    snap_dir = Path(snap_dir)
    snap_dir.mkdir(parents=True, exist_ok=True)
    path = snap_dir / f"{date.isoformat()}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return path
