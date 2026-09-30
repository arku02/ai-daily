import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date as Date, datetime
from pathlib import Path

from . import http, snapshot
from .model import normalize_url
from .sources import SOURCES


@dataclass
class Context:
    date: Date
    now: datetime  # UTC
    warnings: list = field(default_factory=list)


def collect(config, ctx):
    """依序抓取每個來源；單一來源失敗不影響其他來源（R5）。"""
    results = {}
    for name, fetch in SOURCES.items():
        cfg = config.get(name, {})
        if not cfg.get("enabled", True):
            results[name] = {"status": "disabled", "count": 0, "error": None, "items": []}
            continue
        try:
            items = fetch(cfg, ctx)
            results[name] = {"status": "ok", "count": len(items), "error": None, "items": items}
        except (http.FetchError, ET.ParseError, KeyError, TypeError, ValueError) as e:
            results[name] = {"status": "error", "count": 0,
                             "error": http.mask(f"{type(e).__name__}: {e}"), "items": []}
    return results


def dedupe(items):
    """以正規化網址合併；保留最先出現者，其他來源記在 also_in（R4）。"""
    kept = {}
    order = []
    for item in items:
        key = normalize_url(item.url) or f"{item.source}:{item.id}"
        if key in kept:
            kept[key].also_in.append({"source": item.source, "id": item.id, "metrics": item.metrics})
        else:
            kept[key] = item
            order.append(key)
    return [kept[k] for k in order]


def run(config, ctx, out_dir):
    out_dir = Path(out_dir)
    results = collect(config, ctx)
    all_items = [i for r in results.values() for i in r["items"]]

    snap_dir = out_dir / "snapshots"
    today_snap = snapshot.apply_growth(all_items, snapshot.previous(snap_dir, ctx.date))
    snapshot.save(snap_dir, ctx.date, today_snap)

    merged = dedupe(all_items)
    enabled = [r for r in results.values() if r["status"] != "disabled"]
    ok = any(r["status"] == "ok" for r in enabled)

    report = {
        "date": ctx.date.isoformat(),
        "fetched_at": ctx.now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {n: {k: r[k] for k in ("status", "count", "error")} for n, r in results.items()},
        "warnings": [http.mask(w) for w in ctx.warnings],
        "items": [i.to_dict() for i in merged],
    }
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{ctx.date.isoformat()}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report, path, (0 if ok else 1)


def summary_lines(report, path):
    lines = [f"AI 早報抓取 {report['date']}"]
    for name, s in report["sources"].items():
        if s["status"] == "error":
            lines.append(f"  {name:<16} error  {s['error']}")
        else:
            lines.append(f"  {name:<16} {s['status']:<6} {s['count']}")
    for w in report["warnings"]:
        lines.append(f"  warning: {w}")
    lines.append(f"合併後 {len(report['items'])} 項 → {path}")
    return lines
