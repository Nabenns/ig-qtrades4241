"""Manual review test: send pending posts to Telegram + poll callbacks once.

Useful for development without running the long-running scheduler.

Usage:
    uv run python scripts/test_review.py send    # Send all pending review posts
    uv run python scripts/test_review.py poll    # Poll for new callbacks once
    uv run python scripts/test_review.py loop    # Send + poll in a loop (Ctrl+C to stop)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from ig_qt.config import load_config
from ig_qt.db import build_engine, init_schema
from ig_qt.logging_setup import configure_logging
from ig_qt.notifier_review import (
    build_reviewer,
    poll_review_callbacks,
    send_pending_reviews,
)


async def _run(cmd: str) -> int:
    cfg = load_config(Path("config.yaml"))
    configure_logging(log_dir=cfg.paths.data_dir / "logs", level="INFO", json_logs=False)
    engine = build_engine(cfg.paths.data_dir / "ig_qt.db")
    init_schema(engine)

    reviewer = build_reviewer(
        enabled=cfg.notifier.telegram_enabled,
        bot_token=(
            cfg.notifier.telegram_bot_token.get_secret_value()
            if cfg.notifier.telegram_bot_token
            else None
        ),
        chat_id=cfg.notifier.telegram_chat_id,
    )
    if reviewer is None:
        print("Telegram reviewer not configured. Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in .env")
        return 1

    offset_path = cfg.paths.data_dir / "telegram_offset.txt"

    if cmd == "send":
        sent = await send_pending_reviews(engine=engine, reviewer=reviewer)
        print(f"Sent {sent} review message(s).")
        return 0

    if cmd == "poll":
        n = await poll_review_callbacks(
            engine=engine, reviewer=reviewer, update_state_path=offset_path
        )
        print(f"Processed {n} decision(s).")
        return 0

    if cmd == "loop":
        print("Loop mode: send + poll every 10s. Ctrl+C to stop.")
        try:
            while True:
                await send_pending_reviews(engine=engine, reviewer=reviewer)
                await poll_review_callbacks(
                    engine=engine, reviewer=reviewer, update_state_path=offset_path
                )
                await asyncio.sleep(10)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0

    print("Usage: test_review.py [send|poll|loop]")
    return 2


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "loop"
    sys.exit(asyncio.run(_run(cmd)))
