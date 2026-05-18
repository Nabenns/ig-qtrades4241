"""Tests for collector pipeline orchestrator."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from ig_qt.collector.base import NormalizedEvent, NormalizedNews
from ig_qt.collector.pipeline import CollectorPipeline
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Event, RawNews


class _StubNews:
    name = "stub_news"

    async def fetch_news(self) -> Sequence[NormalizedNews]:
        return [
            NormalizedNews(
                source="stub_news",
                external_id="1",
                published_at=datetime(2026, 5, 17, tzinfo=UTC),
                title="Hello World",
                summary=None,
                url="https://x",
                keywords=[],
                raw_payload={},
            ),
        ]


class _FailingNews:
    name = "broken"

    async def fetch_news(self) -> Sequence[NormalizedNews]:
        raise RuntimeError("boom")


class _StubCal:
    name = "stub_cal"

    async def fetch_events(self) -> Sequence[NormalizedEvent]:
        return [
            NormalizedEvent(
                source="stub_cal",
                event_time=datetime(2026, 5, 17, 12, tzinfo=UTC),
                country=None,
                currency="USD",
                name="X",
                impact="high",
                forecast=None,
                previous=None,
                actual=None,
            ),
        ]


@pytest.mark.asyncio
async def test_pipeline_runs_all_sources_isolating_failures(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    pipe = CollectorPipeline(
        engine=engine,
        news_sources=[_StubNews(), _FailingNews()],
        calendar_sources=[_StubCal()],
    )
    result = await pipe.run_once()
    assert result.news_inserted == 1
    assert result.events_inserted == 1
    assert "broken" in result.failed_sources

    with session_scope(engine) as s:
        assert len(s.execute(select(RawNews)).scalars().all()) == 1
        assert len(s.execute(select(Event)).scalars().all()) == 1
