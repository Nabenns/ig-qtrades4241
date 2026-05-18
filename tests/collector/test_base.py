"""Tests for collector base types."""
from __future__ import annotations

from datetime import datetime, timezone

from ig_qt.collector.base import NormalizedEvent, NormalizedNews


def test_normalized_news_dedup_key_stable() -> None:
    n1 = NormalizedNews(
        source="newsapi",
        external_id="x",
        published_at=datetime(2026, 5, 17, 12, tzinfo=timezone.utc),
        title="Fed Holds Rates",
        summary=None,
        url="https://x",
        keywords=["fed", "rates"],
        raw_payload={"a": 1},
    )
    n2 = NormalizedNews(
        source="gnews",
        external_id="y",
        published_at=datetime(2026, 5, 17, 18, tzinfo=timezone.utc),
        title="  fed holds rates ",
        summary="diff",
        url="https://y",
        keywords=[],
        raw_payload={},
    )
    assert n1.dedup_key() == n2.dedup_key()


def test_normalized_event_dedup_key_includes_currency_and_time() -> None:
    e1 = NormalizedEvent(
        source="forex_factory",
        event_time=datetime(2026, 5, 17, 12, 30, tzinfo=timezone.utc),
        country="US",
        currency="USD",
        name="CPI m/m",
        impact="high",
        forecast="0.3%",
        previous="0.4%",
        actual=None,
    )
    assert "USD" not in e1.dedup_key()  # hashed, not literal
    # But same event with same currency+name+time produces same key
    e2 = NormalizedEvent(
        source="other",
        event_time=datetime(2026, 5, 17, 12, 30, tzinfo=timezone.utc),
        country="US",
        currency="USD",
        name="CPI m/m",
        impact="low",
        forecast=None,
        previous=None,
        actual=None,
    )
    assert e1.dedup_key() == e2.dedup_key()
    # Different currency = different key
    e3 = NormalizedEvent(
        source="x", event_time=e1.event_time, country=None, currency="EUR",
        name=e1.name, impact="high", forecast=None, previous=None, actual=None,
    )
    assert e1.dedup_key() != e3.dedup_key()
