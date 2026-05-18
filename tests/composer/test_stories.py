"""Tests for story builders."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ig_qt.composer.stories import build_event_reminder_context, build_market_recap_context


def test_build_event_reminder_filters_high_medium_only() -> None:
    today = datetime(2026, 5, 17, tzinfo=UTC)
    events: list[Any] = [
        type(
            "E",
            (),
            {
                "event_time": today + timedelta(hours=2),
                "currency": "USD",
                "name": "CPI",
                "impact": "high",
                "forecast": "0.3%",
                "previous": "0.4%",
            },
        ),
        type(
            "E",
            (),
            {
                "event_time": today + timedelta(hours=4),
                "currency": "EUR",
                "name": "Speech",
                "impact": "low",
                "forecast": None,
                "previous": None,
            },
        ),
    ]
    ctx = build_event_reminder_context(events=events, now=today)
    assert len(ctx["events"]) == 1
    assert ctx["events"][0]["currency"] == "USD"


def test_build_market_recap_calculates_change() -> None:
    prices = {
        "EUR/USD": [
            {
                "t": "2026-05-16T00:00:00+00:00",
                "open": 1.0800,
                "high": 1.0810,
                "low": 1.0790,
                "close": 1.0850,
            },
            {
                "t": "2026-05-17T00:00:00+00:00",
                "open": 1.0850,
                "high": 1.0880,
                "low": 1.0840,
                "close": 1.0875,
            },
        ],
    }
    ctx = build_market_recap_context(latest_prices=prices, symbols=["EUR/USD"])
    assert len(ctx["recaps"]) == 1
    assert ctx["recaps"][0]["symbol"] == "EUR/USD"
    assert ctx["recaps"][0]["change_pct"] > 0
