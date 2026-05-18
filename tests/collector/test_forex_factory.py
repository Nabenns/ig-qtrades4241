"""Tests for Forex Factory parser."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ig_qt.collector.forex_factory import parse_forex_factory_html


def test_parse_extracts_two_events() -> None:
    fixture = Path(__file__).parent / "fixtures" / "ff_sample.html"
    html = fixture.read_text(encoding="utf-8")
    base_date = datetime(2026, 5, 17, tzinfo=timezone.utc)
    events = parse_forex_factory_html(html, fallback_date=base_date)
    assert len(events) == 2
    cpi = events[0]
    assert cpi.currency == "USD"
    assert cpi.impact == "high"
    assert cpi.name == "CPI m/m"
    assert cpi.forecast == "0.3%"
    ecb = events[1]
    assert ecb.currency == "EUR"
    assert ecb.impact == "medium"
    assert ecb.event_time.date() == base_date.date()
