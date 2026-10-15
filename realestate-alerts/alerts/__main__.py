"""Command line: `python -m alerts [run|setup|test-notify] [options]`."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import notify
from .browser import BrowserSession
from .config import ConfigError, load_config, load_dotenv
from .runner import run_scan
from .setup_env import interactive

ROOT = Path(__file__).resolve().parent.parent


def _setup_logging(log_dir: Path, verbose: bool) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    file = RotatingFileHandler(log_dir / "alerts.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file.setFormatter(fmt)
    root.handlers[:] = [console, file]
    for noisy in ("asyncio", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m alerts",
                                     description="Commercial real-estate alerts for Haifa & Krayot")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "test-notify", "setup"],
                        help="run = scan and notify (default); setup = enter email/WhatsApp details; "
                             "test-notify = send a test message")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--dry-run", action="store_true", help="scan and write the report, but send/save nothing")
    parser.add_argument("--headed", action="store_true", help="show the browser window (solve a captcha once)")
    parser.add_argument("--debug", action="store_true", help="save HTML + screenshot of every page to debug/")
    parser.add_argument("--only", help="comma-separated source names, e.g. yad2,madlan")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # Hebrew on Windows consoles
        except Exception:
            pass

    load_dotenv(ROOT / ".env")
    try:
        cfg = load_config(args.config)
    except (ConfigError, OSError) as exc:
        print(f"Config problem: {exc}", file=sys.stderr)
        return 2
    _setup_logging(cfg.base_dir / "logs", args.verbose)
    log = logging.getLogger("alerts")

    if args.command == "setup":
        updates = interactive(ROOT / ".env")
        os.environ.update({k: v for k, v in updates.items() if v})
        if input("\nSend a test message now? [Y/n]: ").strip().lower() in ("", "y", "yes", "כ", "כן"):
            args.command = "test-notify"
        else:
            return 0

    if args.command == "test-notify":
        active = notify.channels()
        if not active:
            log.error("No channel configured. Fill in .env (see .env.example).")
            return 1
        failed = False
        for channel in active:
            try:
                channel.send_test("✅ Real-estate alerts are connected. / ההתראות מחוברות.")
                log.info("Test sent via %s", channel.name)
            except Exception as exc:
                failed = True
                log.error("%s failed: %s", channel.name, exc)
        return 1 if failed else 0

    only = {s.strip() for s in args.only.split(",")} if args.only else None
    debug_dir = cfg.base_dir / "debug" if args.debug else None
    factory = lambda: BrowserSession(cfg.browser, headed=True if args.headed else None,  # noqa: E731
                                     debug_dir=debug_dir)
    run = run_scan(cfg, factory, only=only, dry_run=args.dry_run)
    if run.sources and all(s.status in ("blocked", "failed") for s in run.sources):
        log.error("Every source failed - see the messages above.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
