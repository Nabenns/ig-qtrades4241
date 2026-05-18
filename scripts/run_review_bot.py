"""Long-running Telegram review bot daemon.

Polls for:
- New posts with status='review' that haven't been sent yet → send to Telegram
- New callback_query updates (button clicks) → process approve/reject

Run with:
    uv run python scripts/run_review_bot.py

Stop with Ctrl+C.
"""
from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

from ig_qt.config import load_config
from ig_qt.db import build_engine, init_schema
from ig_qt.logging_setup import configure_logging
from ig_qt.notifier_review import (
    build_reviewer,
    poll_review_callbacks,
    send_pending_reviews,
)

SEND_INTERVAL_SECONDS = 30  # check for new posts to send every 30s
POLL_INTERVAL_SECONDS = 5  # check for button clicks every 5s


_should_stop = False


def _handle_signal(*_args: object) -> None:
    global _should_stop
    _should_stop = True
    print("\n[review_bot] stopping...")


async def _run() -> int:
    cfg = load_config(Path("config.yaml"))
    log_dir = cfg.paths.data_dir / "logs"
    configure_logging(log_dir=log_dir, level="INFO", json_logs=False)

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
        print("Telegram reviewer not configured. Check .env.")
        return 1

    offset_path = cfg.paths.data_dir / "telegram_offset.txt"

    print("[review_bot] daemon started. Send interval=30s, poll interval=5s.")
    print("[review_bot] Press Ctrl+C to stop.\n")

    last_send = 0.0
    loop = asyncio.get_event_loop()

    while not _should_stop:
        now = loop.time()

        # Periodic: check for new posts to send
        if now - last_send >= SEND_INTERVAL_SECONDS:
            try:
                await send_pending_reviews(engine=engine, reviewer=reviewer)
            except Exception as exc:
                logger.error("review_bot_send_error err={}", exc)
            last_send = now

        # More frequent: poll for callback decisions
        try:
            await poll_review_callbacks(
                engine=engine,
                reviewer=reviewer,
                update_state_path=offset_path,
            )
        except Exception as exc:
            logger.error("review_bot_poll_error err={}", exc)

        # Sleep but check signal flag periodically
        for _ in range(POLL_INTERVAL_SECONDS):
            if _should_stop:
                break
            await asyncio.sleep(1)

    print("[review_bot] stopped cleanly.")
    return 0


def main() -> int:
    # Register signal handlers (Ctrl+C clean shutdown)
    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
