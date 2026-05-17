"""Notifier abstractions: Telegram + no-op."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


@runtime_checkable
class Notifier(Protocol):
    async def send(self, message: str) -> None: ...


class NoopNotifier:
    """Used when notifications disabled."""

    async def send(self, message: str) -> None:
        logger.debug("notifier disabled, dropping message: {}", message[:200])


class TelegramNotifier:
    def __init__(self, *, bot_token: str, chat_id: str, timeout: float = 10.0) -> None:
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._chat_id = chat_id
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def send(self, message: str) -> None:
        # Truncate to Telegram limit (4096) with safety margin.
        text = message[:3900]
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url,
                json={"chat_id": self._chat_id, "text": text, "parse_mode": "Markdown"},
            )
            resp.raise_for_status()
        logger.info("telegram_notify_sent")


def build_notifier(*, enabled: bool, bot_token: str | None, chat_id: str | None) -> Notifier:
    if enabled and bot_token and chat_id:
        return TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    return NoopNotifier()
