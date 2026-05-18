"""Entry point: `python -m ig_qt`."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from ig_qt.app import run_analyze_once, run_check, run_collect_once


def main() -> int:
    parser = argparse.ArgumentParser(prog="ig_qt")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument(
        "--check", action="store_true", help="Alias for `check` subcommand"
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("check", help="Validate env + DB and exit")
    sub.add_parser("collect", help="Run collector once")
    sub.add_parser("analyze", help="Run analyst once")
    args = parser.parse_args()

    if args.check or args.cmd == "check":
        return run_check(config_path=args.config)
    if args.cmd == "collect":
        return asyncio.run(run_collect_once(config_path=args.config))
    if args.cmd == "analyze":
        return asyncio.run(run_analyze_once(config_path=args.config))
    print("ig_qt: scheduler entry point not implemented yet (M5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
