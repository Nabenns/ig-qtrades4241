"""Entry point: `python -m ig_qt`."""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="ig_qt")
    parser.add_argument("--check", action="store_true", help="Validate env/DB and exit")
    args = parser.parse_args()
    if args.check:
        # Wired up in Task 1.8
        print("check: not implemented yet")
        return 0
    print("ig_qt: not implemented yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
