import argparse
import sys
from datetime import date as Date, datetime, timedelta, timezone

from . import config as config_mod
from . import pipeline

# 台灣沒有日光節約時間；用固定時差，避免 Windows 缺 tzdata 時 zoneinfo 失敗
TAIPEI = timezone(timedelta(hours=8), "Asia/Taipei")


def taipei_today(now_utc):
    return now_utc.astimezone(TAIPEI).date()


def build_parser():
    p = argparse.ArgumentParser(prog="python -m ai_daily", description="AI Agent 早報")
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="抓取各來源，輸出 data/raw/<日期>.json")
    f.add_argument("--date", help="YYYY-MM-DD，預設為台北時間今天")
    f.add_argument("--config", default=str(config_mod.DEFAULT_PATH), help="設定檔（預設 sources.toml）")
    f.add_argument("--out", default="data", help="輸出根目錄（預設 data）")
    d = sub.add_parser("digest", help="用 Gemini 篩選並撰寫早報內容，輸出 data/digest/<日期>.json")
    d.add_argument("--date", help="YYYY-MM-DD，預設為台北時間今天")
    d.add_argument("--root", default=".", help="專案根目錄（預設目前目錄）")
    d.add_argument("--dry-run", action="store_true", help="只顯示候選數與提示長度，不呼叫 API")
    return p


def cmd_digest(args, now_utc=None, make_llm=None):
    from .digest import run as digest_run
    now_utc = now_utc or datetime.now(timezone.utc)
    try:
        run_date = Date.fromisoformat(args.date) if args.date else taipei_today(now_utc)
    except ValueError:
        print(f"日期格式錯誤：{args.date}，請用 YYYY-MM-DD", file=sys.stderr)
        return 2
    return digest_run.run(run_date, args.root, args.dry_run, make_llm=make_llm, now=now_utc)


def cmd_fetch(args, now_utc=None):
    now_utc = now_utc or datetime.now(timezone.utc)
    try:
        run_date = Date.fromisoformat(args.date) if args.date else taipei_today(now_utc)
    except ValueError:
        print(f"日期格式錯誤：{args.date}，請用 YYYY-MM-DD", file=sys.stderr)
        return 2
    try:
        cfg = config_mod.load(args.config)
    except config_mod.ConfigError as e:
        print(e, file=sys.stderr)
        return 2
    ctx = pipeline.Context(date=run_date, now=now_utc)
    report, path, code = pipeline.run(cfg, ctx, args.out)
    for line in pipeline.summary_lines(report, path):
        print(line)
    if code:
        print("所有來源都失敗了", file=sys.stderr)
    return code


def main(argv=None, now_utc=None, make_llm=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.command == "fetch":
        return cmd_fetch(args, now_utc)
    if args.command == "digest":
        return cmd_digest(args, now_utc, make_llm)
    return 2
