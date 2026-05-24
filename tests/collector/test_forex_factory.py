"""Tests for Forex Factory JSON-based parser."""
from __future__ import annotations

from ig_qt.collector.forex_factory import _parse_event


def test_parse_high_impact_event() -> None:
    raw = {
        "title": "CPI m/m",
        "country": "USD",
        "date": "2026-05-25T08:30:00-04:00",
        "impact": "High",
        "forecast": "0.3%",
        "previous": "0.2%",
    }
    ev = _parse_event(raw)
    assert ev is not None
    assert ev.currency == "USD"
    assert ev.impact == "high"
    assert ev.name == "CPI m/m"
    assert ev.forecast == "0.3%"
    assert ev.previous == "0.2%"
    # Timezone-aware datetime preserved through dateutil
    assert ev.event_time.tzinfo is not None


def test_parse_medium_impact_event() -> None:
    raw = {
        "title": "ECB Press Conference",
        "country": "EUR",
        "date": "2026-05-26T08:45:00-04:00",
        "impact": "Medium",
        "forecast": "",
        "previous": "",
    }
    ev = _parse_event(raw)
    assert ev is not None
    assert ev.currency == "EUR"
    assert ev.impact == "medium"
    assert ev.forecast is None
    assert ev.previous is None


def test_parse_holiday_normalizes_to_low() -> None:
    raw = {
        "title": "Bank Holiday",
        "country": "CHF",
        "date": "2026-05-25T01:00:00-04:00",
        "impact": "Holiday",
        "forecast": "",
        "previous": "",
    }
    ev = _parse_event(raw)
    assert ev is not None
    assert ev.impact == "low"


def test_parse_returns_none_on_missing_title() -> None:
    raw = {"title": "", "country": "USD", "date": "2026-05-25T08:30:00-04:00"}
    assert _parse_event(raw) is None


def test_parse_returns_none_on_bad_date() -> None:
    raw = {"title": "Test", "country": "USD", "date": "not-a-date"}
    assert _parse_event(raw) is None
