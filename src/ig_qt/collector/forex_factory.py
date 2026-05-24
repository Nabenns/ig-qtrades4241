"""Forex Factory calendar via FairEconomy JSON feed.

Replaces the brittle Playwright HTML scraper with the official JSON endpoint
mirrored by FairEconomy at:
    https://nfs.faireconomy.media/ff_calendar_thisweek.json

The JSON returns ~90 events for the current week. Each row:
    {
        "title": str,
        "country": str (3-letter currency: USD, EUR, ...),
        "date": ISO 8601 datetime with timezone offset,
        "impact": "High" | "Medium" | "Low" | "Holiday",
        "forecast": str | "",
        "previous": str | ""
    }
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC

import httpx
from dateutil import parser as dtparser
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.collector.base import NormalizedEvent

_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Map raw impact strings to our normalized 3-tier scale.
_IMPACT_MAP = {
    "high": "high",
    "medium": "medium",
    "low": "low",
    "holiday": "low",
}


def _parse_event(raw: dict[str, object]) -> NormalizedEvent | None:
    """Convert one FF JSON row into NormalizedEvent. Returns None on bad data."""
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    raw_date = str(raw.get("date") or "").strip()
    if not raw_date:
        return None
    try:
        event_dt = dtparser.parse(raw_date)
    except (ValueError, TypeError):
        return None
    if event_dt.tzinfo is None:
        event_dt = event_dt.replace(tzinfo=UTC)

    raw_impact = str(raw.get("impact") or "").strip().lower()
    impact = _IMPACT_MAP.get(raw_impact, "low")

    currency = str(raw.get("country") or "").strip().upper() or None
    forecast = str(raw.get("forecast") or "").strip() or None
    previous = str(raw.get("previous") or "").strip() or None

    return NormalizedEvent(
        source="forex_factory",
        event_time=event_dt,
        country=None,
        currency=currency,
        name=title,
        impact=impact,
        forecast=forecast,
        previous=previous,
        actual=None,
    )


class ForexFactorySource:
    """Fetch Forex Factory weekly calendar via JSON endpoint.

    Stable, no browser required, Cloudflare-friendly. Returns events for
    the current week (~90 rows).
    """

    name = "forex_factory"

    def __init__(self, *, timezone_id: str = "Asia/Jakarta", timeout: float = 15.0) -> None:
        # timezone_id retained for API compatibility (event timestamps already
        # carry their own offset; no conversion needed here).
        self._timezone_id = timezone_id
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _fetch(self) -> list[dict[str, object]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                _URL, headers={"User-Agent": "Mozilla/5.0 ig-qt"}
            )
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, list):
            raise ValueError(f"unexpected ff json shape: {type(data).__name__}")
        return [row for row in data if isinstance(row, dict)]

    async def fetch_events(self) -> Sequence[NormalizedEvent]:
        try:
            rows = await self._fetch()
        except Exception as exc:
            logger.warning("forex_factory_fetch_failed error={}", exc)
            return []
        events: list[NormalizedEvent] = []
        for row in rows:
            ev = _parse_event(row)
            if ev is not None:
                events.append(ev)
        logger.info("forex_factory_fetched count={}", len(events))
        return events
