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
    r = sub.add_parser("render", help="把 data/digest/*.json 產生成 site/ 網頁")
    r.add_argument("--root", default=".", help="專案根目錄（預設目前目錄）")
    pu = sub.add_parser("push", help="推送今天的重點到 Telegram")
    pu.add_argument("--date", help="YYYY-MM-DD，預設為台北時間今天")
    pu.add_argument("--root", default=".", help="專案根目錄（預設目前目錄）")
    pu.add_argument("--dry-run", action="store_true", help="只印出訊息，不送出")
    pu.add_argument("--force", action="store_true", help="已推送過也再送一次")
    co = sub.add_parser("collect", help="從 Telegram 收回饋，存到回饋資料夾")
    co.add_argument("--root", default=".", help="專案根目錄（預設目前目錄）")
    return p


def _publish_cfg(root):
    import tomllib
    from pathlib import Path
    path = Path(root) / "publish.toml"
    with path.open("rb") as f:
        return tomllib.load(f)


def _bot(root, make_bot):
    from . import env
    token = env.get("TELEGRAM_BOT_TOKEN", root)
    chat_id = env.get("TELEGRAM_CHAT_ID", root)
    if not token or not chat_id:
        print("找不到 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID：請在專案根目錄的 .env 設定", file=sys.stderr)
        return None
    if make_bot:
        return make_bot(token, chat_id)
    from .publish.telegram import Bot
    return Bot(token, chat_id)


def cmd_render(args):
    from .publish import html
    cfg = _publish_cfg(args.root)
    result = html.render_all(args.root, cfg.get("telegram", {}).get("bot_username", ""))
    if result is None:
        print("data/digest 沒有任何早報，請先執行 python -m ai_daily digest", file=sys.stderr)
        return 2
    site, dates = result
    print(f"產生 {len(dates)} 天的網頁（最新 {dates[0]}）→ {site.as_posix()}/index.html")
    return 0


def cmd_push(args, now_utc=None, make_bot=None):
    import json
    from pathlib import Path
    from .publish import push as push_mod
    from .publish.telegram import TelegramError
    now_utc = now_utc or datetime.now(timezone.utc)
    try:
        run_date = Date.fromisoformat(args.date) if args.date else taipei_today(now_utc)
    except ValueError:
        print(f"日期格式錯誤：{args.date}，請用 YYYY-MM-DD", file=sys.stderr)
        return 2
    path = Path(args.root) / "data" / "digest" / f"{run_date.isoformat()}.json"
    if not path.is_file():
        print(f"找不到 {path.as_posix()}，請先執行 digest", file=sys.stderr)
        return 2
    digest = json.loads(path.read_text(encoding="utf-8"))
    base_url = _publish_cfg(args.root)["site"]["base_url"]
    bot = None
    if not args.dry_run:
        bot = _bot(args.root, make_bot)
        if bot is None:
            return 2
    try:
        return push_mod.push(bot, digest, base_url, args.root, args.force, args.dry_run, now=now_utc)
    except TelegramError as e:
        print(e, file=sys.stderr)
        return 1


def cmd_collect(args, now_utc=None, make_bot=None):
    import os
    from pathlib import Path
    from .publish import collect as collect_mod
    from .publish.telegram import TelegramError
    bot = _bot(args.root, make_bot)
    if bot is None:
        return 2
    folder = os.environ.get("FEEDBACK_DIR") or _publish_cfg(args.root).get("feedback", {}).get("dir", "feedback")
    folder = Path(folder) if Path(folder).is_absolute() else Path(args.root) / folder
    try:
        collect_mod.collect(bot, args.root, folder, now=now_utc)
    except TelegramError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


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


def main(argv=None, now_utc=None, make_llm=None, make_bot=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.command == "fetch":
        return cmd_fetch(args, now_utc)
    if args.command == "digest":
        return cmd_digest(args, now_utc, make_llm)
    if args.command == "render":
        return cmd_render(args)
    if args.command == "push":
        return cmd_push(args, now_utc, make_bot)
    if args.command == "collect":
        return cmd_collect(args, now_utc, make_bot)
    return 2
