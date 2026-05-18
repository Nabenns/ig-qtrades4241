"""NewsAPI.org adapter."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
from dateutil import parser as dtparser
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.collector.base import NormalizedNews

_BASE = "https://newsapi.org/v2/everything"


class NewsAPISource:
    name = "newsapi"

    def __init__(
        self,
        *,
        api_key: str,
        keywords: Sequence[str] | None = None,
        page_size: int = 50,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._keywords = list(keywords) if keywords else ["forex", "fed", "ecb", "boe", "boj"]
        self._page_size = page_size
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _get(self) -> dict[str, Any]:
        query = " OR ".join(self._keywords)
        params: dict[str, Any] = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": self._page_size,
            "apiKey": self._api_key,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(_BASE, params=params)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data

    async def fetch_news(self) -> Sequence[NormalizedNews]:
        try:
            data = await self._get()
        except Exception as exc:
            logger.warning("newsapi_fetch_failed error={}", exc)
            return []
        if data.get("status") != "ok":
            logger.warning("newsapi_status_not_ok body={}", data)
            return []
        items: list[NormalizedNews] = []
        for art in data.get("articles", []):
            title = (art.get("title") or "").strip()
            if not title or title == "[Removed]":
                continue
            published = art.get("publishedAt")
            published_dt: datetime | None = None
            if published:
                try:
                    parsed = dtparser.isoparse(published)
                    published_dt = (
                        parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
                    )
                except (ValueError, TypeError):
                    published_dt = None
            url = art.get("url") or ""
            items.append(
                NormalizedNews(
                    source=self.name,
                    external_id=url or None,
                    published_at=published_dt,
                    title=title,
                    summary=art.get("description"),
                    url=url,
                    keywords=list(self._keywords),
                    raw_payload=art,
                )
            )
        logger.info("newsapi_fetched count={}", len(items))
        return items
