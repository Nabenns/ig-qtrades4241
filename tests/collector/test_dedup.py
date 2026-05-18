"""Tests for dedup helpers."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from ig_qt.collector.base import NormalizedEvent, NormalizedNews
from ig_qt.collector.dedup import insert_events_dedup, insert_news_dedup
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Event, RawNews


def test_insert_news_dedup_skips_duplicates(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)

    n1 = NormalizedNews(
        source="newsapi",
        external_id="1",
        published_at=datetime(2026, 5, 17, tzinfo=UTC),
        title="Fed Holds Rates",
        summary=None,
        url="https://x",
        keywords=[],
        raw_payload={},
    )
    n2 = NormalizedNews(
        source="gnews",
        external_id="2",
        published_at=datetime(2026, 5, 17, 12, tzinfo=UTC),
        title="fed holds rates",
        summary=None,
        url="https://y",
        keywords=[],
        raw_payload={},
    )

    with session_scope(engine) as s:
        inserted = insert_news_dedup(s, [n1, n2])
    assert inserted == 1

    with session_scope(engine) as s:
        rows = s.execute(select(RawNews)).scalars().all()
    assert len(rows) == 1


def test_insert_events_dedup(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)

    e1 = NormalizedEvent(
        source="ff",
        event_time=datetime(2026, 5, 17, 12, 30, tzinfo=UTC),
        country="US",
        currency="USD",
        name="CPI m/m",
        impact="high",
        forecast="0.3%",
        previous="0.4%",
        actual=None,
    )
    with session_scope(engine) as s:
        inserted = insert_events_dedup(s, [e1, e1])
    assert inserted == 1

    with session_scope(engine) as s:
        rows = s.execute(select(Event)).scalars().all()
    assert len(rows) == 1
