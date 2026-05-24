"""RSS feed adapter for forex/finance news sources.

Free, no API key required, no rate limits. Used as supplement to NewsAPI/GNews
to provide more realtime headlines.
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

import feedparser
from loguru import logger

from ig_qt.collector.base import NormalizedNews

# Default RSS sources for forex/finance news.
# Verified live as of 2026-05. Drop entries that return SSL/cert errors.
DEFAULT_RSS_FEEDS: tuple[str, ...] = (
    # ForexLive — primary, very fast updates, forex-focused
    "https://www.forexlive.com/feed/news",
    # Investing.com — forex news (curated)
    "https://www.investing.com/rss/news_25.rss",
    # FinanceMagnates — forex/CFD industry news
    "https://www.financemagnates.com/feed/",
    # CNBC — broad market + macro coverage
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    # MarketWatch — top stories, macro adjacent
    "https://www.marketwatch.com/rss/topstories",
)


class RSSSource:
    """Aggregate RSS feeds, normalize to NormalizedNews."""

    name = "rss"

    def __init__(
        self,
        *,
        feeds: Sequence[str] | None = None,
        timeout: float = 20.0,
        max_per_feed: int = 15,
    ) -> None:
        self._feeds = list(feeds) if feeds else list(DEFAULT_RSS_FEEDS)
        self._timeout = timeout
        self._max_per_feed = max_per_feed

    async def _parse_one(self, url: str) -> list[NormalizedNews]:
        """Parse a single RSS feed in a thread (feedparser is sync)."""
        try:
            parsed = await asyncio.wait_for(
                asyncio.to_thread(feedparser.parse, url),
                timeout=self._timeout,
            )
        except TimeoutError:
            logger.warning("rss_timeout url={}", url)
            return []
        except Exception as exc:
            logger.warning("rss_parse_failed url={} err={}", url, exc)
            return []

        if parsed.bozo and not parsed.entries:
            # bozo flag set + no entries = real failure
            logger.warning("rss_bozo url={} err={}", url, parsed.bozo_exception)
            return []

        items: list[NormalizedNews] = []
        for entry in parsed.entries[: self._max_per_feed]:
            entry = cast(dict[str, Any], entry)
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            link = entry.get("link") or ""
            summary = entry.get("summary") or entry.get("description") or None
            # Try multiple datetime fields
            published_dt = _parse_entry_datetime(entry)
            items.append(
                NormalizedNews(
                    source=f"rss_{_short_host(url)}",
                    external_id=link or None,
                    published_at=published_dt,
                    title=title,
                    summary=summary,
                    url=link,
                    keywords=[],
                    raw_payload=dict(entry),
                )
            )
        logger.debug("rss_parsed url={} items={}", url, len(items))
        return items

    async def fetch_news(self) -> Sequence[NormalizedNews]:
        # Run all feeds in parallel
        results = await asyncio.gather(
            *(self._parse_one(url) for url in self._feeds), return_exceptions=True
        )
        all_items: list[NormalizedNews] = []
        for r in results:
            if isinstance(r, list):
                all_items.extend(r)
        logger.info("rss_fetched count={} feeds={}", len(all_items), len(self._feeds))
        return all_items


def _short_host(url: str) -> str:
    """Extract a short hostname tag (e.g. 'forexlive') from a feed URL."""
    try:
        from urllib.parse import urlparse

        host = urlparse(url).netloc.lower()
        # Strip www. and TLDs to get the brand
        host = host.removeprefix("www.")
        return host.split(".")[0]
    except Exception:
        return "unknown"


def _parse_entry_datetime(entry: dict[str, Any]) -> datetime | None:
    """Try multiple feedparser datetime fields, normalize to UTC."""
    # Preferred: published_parsed (struct_time)
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(
                    st[0], st[1], st[2], st[3], st[4], st[5], tzinfo=UTC
                )
            except (TypeError, ValueError):
                continue
    # Fallback: parse text via dateutil
    for key in ("published", "updated"):
        text = entry.get(key)
        if text:
            try:
                from dateutil import parser as dtparser

                parsed = dtparser.parse(text)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed
            except (ValueError, TypeError):
                continue
    return None
