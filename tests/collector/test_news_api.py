"""Tests for NewsAPI adapter."""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from ig_qt.collector.news_api import NewsAPISource


@pytest.mark.asyncio
async def test_news_api_fetches_and_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = {
        "status": "ok",
        "articles": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "title": "Fed Holds Rates Steady",
                "description": "FOMC kept...",
                "url": "https://example.com/a",
                "publishedAt": "2026-05-17T12:00:00Z",
                "content": "Long content",
            },
            {
                "source": {"name": "Bloomberg"},
                "title": "ECB Signals Cut",
                "description": None,
                "url": "https://example.com/b",
                "publishedAt": "2026-05-17T13:00:00Z",
                "content": None,
            },
        ],
    }

    async def fake_get(self: Any, url: str, params: Any = None, **_: Any) -> Any:
        class R:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, Any]:
                return sample

        return R()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    src = NewsAPISource(api_key="k", keywords=["forex", "fed"])
    items = await src.fetch_news()
    assert len(items) == 2
    assert items[0].title == "Fed Holds Rates Steady"
    assert items[0].source == "newsapi"
    assert items[0].published_at is not None
