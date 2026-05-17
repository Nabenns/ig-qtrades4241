"""Tests for Telegram notifier."""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from ig_qt.notifier import NoopNotifier, TelegramNotifier


@pytest.mark.asyncio
async def test_noop_notifier_does_nothing() -> None:
    n = NoopNotifier()
    await n.send("anything")  # should not raise


@pytest.mark.asyncio
async def test_telegram_notifier_posts_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_post(self: Any, url: str, json: dict[str, Any], **_: Any) -> Any:
        captured["url"] = url
        captured["json"] = json

        class R:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

        return R()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    n = TelegramNotifier(bot_token="token-x", chat_id="123")
    await n.send("hello")
    assert captured["url"] == "https://api.telegram.org/bottoken-x/sendMessage"
    assert captured["json"] == {"chat_id": "123", "text": "hello", "parse_mode": "Markdown"}
