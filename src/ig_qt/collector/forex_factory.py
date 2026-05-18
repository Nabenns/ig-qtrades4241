"""Forex Factory calendar scraper via Playwright."""
from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime

from bs4 import BeautifulSoup, Tag
from dateutil import parser as dtparser
from loguru import logger

from ig_qt.collector.base import NormalizedEvent
from ig_qt.collector.playwright_runner import browser_session

_URL = "https://www.forexfactory.com/calendar"
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(am|pm)$", re.IGNORECASE)
_IMPACT_CLASS = re.compile(r"impact--(high|medium|low|holiday)")


def _impact_from_classes(td: Tag) -> str:
    span = td.find("span", class_=re.compile(r"impact"))
    if not isinstance(span, Tag):
        return "low"
    raw_classes = span.get("class")
    if raw_classes is None:
        return "low"
    classes = (
        raw_classes if isinstance(raw_classes, str) else " ".join(str(c) for c in raw_classes)
    )
    m = _IMPACT_CLASS.search(classes)
    if not m:
        return "low"
    return m.group(1) if m.group(1) != "holiday" else "low"


def _text(td: Tag | None) -> str:
    return td.get_text(strip=True) if td else ""


def parse_forex_factory_html(html: str, *, fallback_date: datetime) -> list[NormalizedEvent]:
    """Parse Forex Factory calendar HTML into NormalizedEvent list."""
    soup = BeautifulSoup(html, "html.parser")
    events: list[NormalizedEvent] = []
    current_date = fallback_date.date()
    for row in soup.select("tr.calendar__row"):
        if not isinstance(row, Tag):
            continue
        date_td = row.find("td", class_="calendar__date")
        date_text = _text(date_td if isinstance(date_td, Tag) else None)
        if date_text:
            try:
                parsed = dtparser.parse(f"{date_text} {fallback_date.year}")
                current_date = parsed.date()
            except (ValueError, TypeError):
                pass
        time_td = row.find("td", class_="calendar__time")
        currency_td = row.find("td", class_="calendar__currency")
        event_td = row.find("td", class_="calendar__event")
        forecast_td = row.find("td", class_="calendar__forecast")
        previous_td = row.find("td", class_="calendar__previous")
        actual_td = row.find("td", class_="calendar__actual")
        impact_td = row.find("td", class_="calendar__impact")

        time_text = _text(time_td if isinstance(time_td, Tag) else None)
        currency = _text(currency_td if isinstance(currency_td, Tag) else None).upper() or None
        name = _text(event_td if isinstance(event_td, Tag) else None)
        if not name:
            continue
        impact = (
            _impact_from_classes(impact_td) if isinstance(impact_td, Tag) else "low"
        )
        forecast = _text(forecast_td if isinstance(forecast_td, Tag) else None) or None
        previous = _text(previous_td if isinstance(previous_td, Tag) else None) or None
        actual = _text(actual_td if isinstance(actual_td, Tag) else None) or None

        if time_text and _TIME_RE.match(time_text):
            try:
                event_dt_naive = dtparser.parse(f"{current_date.isoformat()} {time_text}")
                event_dt = event_dt_naive.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                event_dt = datetime.combine(current_date, datetime.min.time(), tzinfo=UTC)
        else:
            event_dt = datetime.combine(current_date, datetime.min.time(), tzinfo=UTC)

        events.append(
            NormalizedEvent(
                source="forex_factory",
                event_time=event_dt,
                country=None,
                currency=currency,
                name=name,
                impact=impact,
                forecast=forecast,
                previous=previous,
                actual=actual,
            )
        )
    return events


class ForexFactorySource:
    name = "forex_factory"

    def __init__(self, *, timezone_id: str = "Asia/Jakarta") -> None:
        self._timezone_id = timezone_id

    async def fetch_events(self) -> Sequence[NormalizedEvent]:
        try:
            async with browser_session(timezone_id=self._timezone_id) as ctx:
                page = await ctx.new_page()
                await page.goto(_URL, wait_until="networkidle", timeout=45_000)
                await page.wait_for_selector("table.calendar__table", timeout=15_000)
                html = await page.content()
        except Exception as exc:
            logger.warning("forex_factory_fetch_failed error={}", exc)
            return []
        events = parse_forex_factory_html(html, fallback_date=datetime.now(UTC))
        logger.info("forex_factory_fetched count={}", len(events))
        return events
