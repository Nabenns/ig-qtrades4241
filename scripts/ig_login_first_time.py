"""Interactive first-time IG login. Handles ChallengeRequired (email/SMS code).

Usage:
    uv run python scripts/ig_login_first_time.py

Reads username/password from .env (IG_USERNAME / IG_PASSWORD).
Prompts for verification code if Instagram requests it.
Saves session to data/ig_session.json.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

# Auto-load .env so this script can be run standalone
from ig_qt.config import _load_dotenv_if_present

_load_dotenv_if_present()


def main() -> int:
    try:
        from instagrapi import Client
        from instagrapi.exceptions import ChallengeRequired
    except ImportError as exc:
        print(f"instagrapi not installed: {exc}")
        return 1

    username = os.environ.get("IG_USERNAME")
    password = os.environ.get("IG_PASSWORD")
    if not username or not password:
        print("Set IG_USERNAME and IG_PASSWORD in .env first.")
        return 2

    data_dir = Path(os.environ.get("IG_QT_DATA_DIR", "data"))
    session_path = data_dir / "ig_session.json"
    backups_dir = data_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    cl = Client()
    cl.delay_range = [2, 5]

    def challenge_code_handler(_username: str, _choice: str) -> str:
        return input("Enter verification code from email/SMS: ").strip()

    cl.challenge_code_handler = challenge_code_handler

    try:
        cl.login(username, password)
    except ChallengeRequired:
        print("Challenge required, follow prompts...")
        last_json: Any = cl.last_json
        cl.challenge_resolve(last_json)
        cl.login(username, password)

    session_path.parent.mkdir(parents=True, exist_ok=True)
    cl.dump_settings(session_path)
    backup_path = backups_dir / f"ig_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_path.write_text(session_path.read_text())
    logger.info(
        "first_time_login_done session_path={} backup={}", session_path, backup_path
    )
    print(f"Session saved to {session_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
