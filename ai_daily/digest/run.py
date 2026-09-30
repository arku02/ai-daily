"""R6：把候選準備、選題、補充、寫作串起來，輸出 data/digest/<日期>.json。"""

import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from . import candidates as cand
from . import enrich as enrich_mod
from . import select, write
from .llm import BadResponse, Gemini, LLMError, load_key


def _toml(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_profile(root):
    root = Path(root)
    if (root / "profile.toml").is_file():
        return _toml(root / "profile.toml"), False
    return _toml(root / "profile.example.toml"), True


def run(date, root=".", dry_run=False, make_llm=None, now=None, out=None):
    out = out or (lambda *a: print(*a))
    root = Path(root)
    raw_path = root / "data" / "raw" / f"{date.isoformat()}.json"
    if not raw_path.is_file():
        out(f"找不到 {raw_path.as_posix()}，請先執行 python -m ai_daily fetch --date {date.isoformat()}")
        return 2
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    cfg = _toml(root / "digest.toml")
    profile, is_example = load_profile(root)
    if is_example:
        out("使用 profile.example.toml；可以複製成 profile.toml 改成你自己的背景（不會被上傳）")

    cands = cand.pick(raw, cfg.get("candidates", {}))
    by_ref = {c.ref: c for c in cands}
    lines = cand.compact_lines(cands, int(cfg.get("candidates", {}).get("summary_chars", 220)))
    caps = cfg["sections"]
    prompt = select.build_prompt(lines, profile, caps, date.isoformat())

    counts = {}
    for c in cands:
        counts[c.item["source"]] = counts.get(c.item["source"], 0) + 1
    out(f"候選 {len(cands)} 筆：" + "、".join(f"{k} {v}" for k, v in counts.items()))
    if dry_run:
        out(f"選題提示 {len(prompt)} 字元（dry-run：沒有呼叫 API、沒有寫檔）")
        return 0

    llm_cfg = cfg.get("llm", {})
    if make_llm is None:
        key = load_key(root)
        if not key:
            out("找不到 GEMINI_API_KEY：請在專案根目錄的 .env 寫入 GEMINI_API_KEY=你的key")
            return 2
        llm = Gemini(key, llm_cfg.get("models", []), float(llm_cfg.get("temperature", 0.4)),
                     int(llm_cfg.get("timeout", 180)))
    else:
        llm = make_llm(llm_cfg)

    warnings = []
    try:
        selection = None
        for _ in range(2):
            try:
                selection = select.validate(llm.generate_json(prompt), set(by_ref), caps)
                break
            except BadResponse as e:
                warnings.append(f"select: {e}")
        if selection is None:
            out("選題失敗：模型兩次都沒有回傳可用的 JSON")
            return 1

        max_chars = int(cfg.get("enrich", {}).get("max_chars", 3000))
        try_chars = int(cfg.get("enrich", {}).get("try_one_max_chars", max_chars))
        limits = {r: max_chars for s in selection["sections"].values() for r in s["items"]}
        for r in selection["try_one"]:
            limits[r] = max(limits.get(r, 0), try_chars)
        texts, try_texts = {}, {}
        for ref, limit in limits.items():
            text, ok = enrich_mod.enrich(by_ref[ref].item, limit)
            texts[ref] = text[:max_chars]
            try_texts[ref] = text
            if not ok:
                warnings.append(f"enrich: {ref} 補充內容抓取失敗，改用原始摘要")

        sections = {}
        for name, sel in selection["sections"].items():
            items, briefs = write.write_section(
                llm, name, [by_ref[r] for r in sel["items"]], [by_ref[r] for r in sel["brief"]],
                texts, profile, date.isoformat(), warnings)
            sections[name] = {"items": items, "brief": briefs}

        try_one = None
        for ref in selection["try_one"]:
            c = by_ref[ref]
            try_one = write.write_try_one(llm, c, try_texts.get(c.ref, ""), profile, date.isoformat(), warnings)
            if try_one is not None:
                break
    except LLMError as e:
        out(f"呼叫模型失敗：{llm.mask(e) if hasattr(llm, 'mask') else e}")
        return 1

    now = now or datetime.now(timezone.utc)
    digest = {
        "date": date.isoformat(),
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "models_used": list(llm.models_used),
        "llm_calls": llm.calls,
        "tldr": selection["tldr"],
        "sections": sections,
        "try_one": try_one,
        "warnings": warnings,
    }
    out_dir = root / "data" / "digest"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{date.isoformat()}.json"
    path.write_text(json.dumps(digest, ensure_ascii=False, indent=1), encoding="utf-8")

    n_items = sum(len(s["items"]) for s in sections.values())
    n_brief = sum(len(s["brief"]) for s in sections.values())
    n_fb = sum(x["fallback"] for s in sections.values() for x in s["items"] + s["brief"])
    out(f"深度 {n_items} 則、快速瀏覽 {n_brief} 則、今天試一個 {'有' if try_one else '無'}；"
        f"降級 {n_fb} 則；模型呼叫 {llm.calls} 次（{', '.join(llm.models_used) or '無'}）")
    for w in warnings:
        out(f"  warning: {w}")
    out(f"→ {path.as_posix()}")
    return 0
