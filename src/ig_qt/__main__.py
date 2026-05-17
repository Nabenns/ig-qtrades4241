"""Entry point: `python -m ig_qt`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ig_qt.app import run_check


def main() -> int:
    parser = argparse.ArgumentParser(prog="ig_qt")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate env + initialize DB and exit",
    )
    args = parser.parse_args()
    if args.check:
        return run_check(config_path=args.config)
    print("ig_qt: scheduler entry point not implemented yet (M5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
