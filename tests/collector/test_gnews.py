"""Tests for GNews adapter."""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from ig_qt.collector.gnews import GNewsSource


@pytest.mark.asyncio
async def test_gnews_fetches_and_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = {
        "totalArticles": 2,
        "articles": [
            {
                "title": "USD Strengthens After CPI",
                "description": "...",
                "content": "...",
                "url": "https://x.example/1",
                "image": "https://x.example/img.jpg",
                "publishedAt": "2026-05-17T12:00:00Z",
                "source": {"name": "Reuters", "url": "https://reuters.com"},
            },
            {
                "title": "Gold Hits New High",
                "description": "...",
                "content": "...",
                "url": "https://x.example/2",
                "image": None,
                "publishedAt": "2026-05-17T11:00:00Z",
                "source": {"name": "Bloomberg", "url": "https://bloomberg.com"},
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
    src = GNewsSource(api_key="k", keywords=["forex"])
    items = await src.fetch_news()
    assert len(items) == 2
    assert items[0].source == "gnews"
    assert items[0].title.startswith("USD")
