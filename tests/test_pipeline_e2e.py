"""End-to-end pipeline integration tests.

Validates the chain collector_pipeline → analyst → metrics + variability +
pipeline_health alerts work together against a real SQLite engine but with
all external services (LLM, image gen, Telegram, HTTP collectors) mocked.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from ig_qt.analyst.runner import AnalystRunner
from ig_qt.caption_variability import analyze_variability
from ig_qt.collector.base import NormalizedEvent, NormalizedNews, NormalizedPrice
from ig_qt.collector.pipeline import CollectorPipeline
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.llm.base import LLMResponse
from ig_qt.metrics import collect_weekly_metrics
from ig_qt.models import EvergreenDraft, Post, PostDraft
from ig_qt.pipeline_health import (
    alert_analyst_if_degraded,
    alert_collect_if_degraded,
    evaluate_collect,
)


class _StubNewsSource:
    name = "stub_news"

    def __init__(self, items: list[NormalizedNews]) -> None:
        self._items = items

    async def fetch_news(self) -> Sequence[NormalizedNews]:
        return self._items


class _StubCalendarSource:
    name = "stub_cal"

    def __init__(self, items: list[NormalizedEvent]) -> None:
        self._items = items

    async def fetch_events(self) -> Sequence[NormalizedEvent]:
        return self._items


class _StubPriceSource:
    name = "stub_prices"

    def __init__(self, prices: dict[str, list[dict[str, Any]]]) -> None:
        self._prices = prices

    async def fetch_ohlc(
        self, symbol: str, timeframe: str, limit: int
    ) -> NormalizedPrice:
        ohlc = self._prices.get(symbol, [])
        return NormalizedPrice(
            symbol=symbol, timeframe=timeframe, fetched_at=datetime.now(UTC), ohlc=ohlc
        )


class _StubLLM:
    """Returns a high-confidence ranker output then a valid AngleDraft per call."""

    name = "stub_llm"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete_json(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        sys = kwargs.get("system", "")
        if "Rank" in sys or "ranked" in sys.lower():
            payload: dict[str, Any] = {
                "ranked": [{"id": 1, "score": 0.92, "reason": "highest impact"}]
            }
        else:
            payload = {
                "post_type": "feed" if "feed" in kwargs["user"][:200] else "story",
                "topic_tag": "fed_hawkish_pivot",
                "angle": "Fed hawkish pivot tightens dollar liquidity",
                "key_points": ["DXY firms", "Yields up", "Risk off"],
                "caption_draft": "Update pasar hari ini: " + ("x" * 240),
                "visual_spec": {
                    "type": "headline",
                    "headline": "Fed Hawkish Pivot",
                    "highlight_phrase": "Hawkish",
                    "highlight_color": "amber",
                },
                "dynamic_hashtags": ["#fed", "#usd", "#macro"],
                "disclaimer_required": True,
                "confidence": 0.88,
            }
        return LLMResponse(
            content=json.dumps(payload),
            parsed=payload,
            model=kwargs["model"],
            input_tokens=100,
            output_tokens=200,
        )

    async def complete_text(self, **kwargs: Any) -> LLMResponse:  # pragma: no cover
        raise NotImplementedError


class _RecordingNotifier:
    """Captures messages instead of sending."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, message: str) -> None:
        self.messages.append(message)


def _seed_published_posts(engine: Any, *, count: int = 6) -> None:
    """Pre-populate Post rows for metrics + variability tests."""
    with session_scope(engine) as s:
        for i in range(count):
            s.add(
                Post(
                    draft_id=None,
                    post_type="feed",
                    caption_final=(
                        "Update pasar hari ini:\nFed bicara hawkish.\n#qtradesedu"
                    ),
                    hashtags=["#qtradesedu"],
                    asset_path=f"./fake-asset-{i}.jpg",
                    visual_type="headline",
                    scheduled_for=datetime.now(UTC),
                    status="approved",
                )
            )


@pytest.mark.asyncio
async def test_full_pipeline_collect_then_analyze(tmp_path: Path) -> None:
    """Collector inserts news+events+prices, analyst produces a feed draft."""
    engine = build_engine(tmp_path / "e2e.db")
    init_schema(engine)

    news = [
        NormalizedNews(
            source="stub_news",
            external_id="1",
            published_at=datetime.now(UTC),
            title="Fed Hikes Rates Citing Inflation",
            summary="Hawkish tone",
            url="https://example.com/1",
            keywords=["fed", "rates"],
            raw_payload={},
        )
    ]
    events = [
        NormalizedEvent(
            source="stub_cal",
            event_time=datetime.now(UTC) + timedelta(hours=4),
            country="US",
            currency="USD",
            name="CPI m/m",
            impact="high",
            forecast="0.3%",
            previous="0.2%",
            actual=None,
        )
    ]
    prices = {
        "EUR/USD": [
            {
                "t": "2026-05-24T10:00:00+00:00",
                "open": 1.085, "high": 1.087, "low": 1.084, "close": 1.086,
            },
            {
                "t": "2026-05-24T11:00:00+00:00",
                "open": 1.086, "high": 1.088, "low": 1.085, "close": 1.087,
            },
        ]
    }

    pipeline = CollectorPipeline(
        engine=engine,
        news_sources=[_StubNewsSource(news)],
        calendar_sources=[_StubCalendarSource(events)],
        price_source=_StubPriceSource(prices),
        price_symbols=["EUR/USD"],
        price_timeframe="1h",
    )
    result = await pipeline.run_once()
    assert result.news_inserted == 1
    assert result.events_inserted == 1
    assert result.prices_cached == 1
    assert result.failed_sources == []

    # Now run analyst against the freshly-collected data.
    runner = AnalystRunner(
        engine=engine,
        provider=_StubLLM(),
        ranker_model="r",
        composer_model="c",
        story_count=0,
        confidence_threshold=0.6,
    )
    summary = await runner.run_once(today=datetime.now(UTC))
    assert summary.feed_drafts == 1
    assert summary.evergreen_used is False
    assert summary.stale_inputs is False
    assert summary.freshest_news_age_hours is not None
    assert summary.freshest_news_age_hours < 1.0

    with session_scope(engine) as s:
        drafts = s.query(PostDraft).all()
        assert len(drafts) == 1
        assert drafts[0].post_type == "feed"
        assert drafts[0].confidence >= 0.6


@pytest.mark.asyncio
async def test_pipeline_health_alerts_on_degradation(tmp_path: Path) -> None:
    """When collector returns 0 news, alert helper should send a Telegram message."""
    engine = build_engine(tmp_path / "e2e2.db")
    init_schema(engine)

    pipeline = CollectorPipeline(
        engine=engine,
        news_sources=[_StubNewsSource([])],  # empty
        calendar_sources=[],
        price_source=None,
        price_symbols=[],
    )
    result = await pipeline.run_once()
    assert result.news_inserted == 0

    notifier = _RecordingNotifier()
    await alert_collect_if_degraded(notifier=notifier, result=result)
    assert len(notifier.messages) == 1
    assert "news_inserted=0" in notifier.messages[0]

    # evaluate_collect classifies independently
    a = evaluate_collect(result)
    assert a.no_news is True
    assert a.is_degraded is True


@pytest.mark.asyncio
async def test_analyst_alerts_on_evergreen_fallback(tmp_path: Path) -> None:
    """Analyst with empty inputs but evergreen present → alerts mention fallback."""
    engine = build_engine(tmp_path / "e2e3.db")
    init_schema(engine)

    with session_scope(engine) as s:
        s.add(
            EvergreenDraft(
                topic_tag="risk_basics",
                angle="Risk management basics",
                key_points=["a"],
                caption_draft="x" * 200,
                visual_spec={"type": "headline", "headline": "Risk Basics"},
                disclaimer_required=True,
            )
        )

    runner = AnalystRunner(
        engine=engine,
        provider=_StubLLM(),
        ranker_model="r",
        composer_model="c",
        story_count=0,
        confidence_threshold=0.6,
    )
    summary = await runner.run_once(today=datetime.now(UTC))
    # No news in DB → stale + evergreen fallback
    assert summary.evergreen_used is True
    assert summary.stale_inputs is True

    notifier = _RecordingNotifier()
    await alert_analyst_if_degraded(notifier=notifier, summary=summary)
    assert len(notifier.messages) == 1
    msg = notifier.messages[0]
    assert "evergreen" in msg.lower() or "stale" in msg.lower() or "empty" in msg.lower()


def test_metrics_and_variability_against_seeded_posts(tmp_path: Path) -> None:
    """Metrics + variability return sensible numbers from seeded posts."""
    engine = build_engine(tmp_path / "e2e4.db")
    init_schema(engine)
    _seed_published_posts(engine, count=6)

    m = collect_weekly_metrics(engine, days=7)
    assert m.posts_total == 6
    assert m.posts_approved == 6
    assert m.posts_rejected == 0

    r = analyze_variability(engine, days=7)
    assert r.sample_size == 6
    # All 6 posts share the same opener "update pasar hari ini" → repetitive flag
    assert r.is_repetitive is True
    assert r.top_openers[0].share == 1.0


@pytest.mark.asyncio
async def test_alert_debounces_until_min_consecutive(tmp_path: Path) -> None:
    """First two empty-collect runs do NOT alert; the third does."""
    engine = build_engine(tmp_path / "e2e5.db")
    init_schema(engine)

    pipeline = CollectorPipeline(
        engine=engine,
        news_sources=[_StubNewsSource([])],
        calendar_sources=[],
        price_source=None,
        price_symbols=[],
    )

    notifier = _RecordingNotifier()

    for _ in range(2):
        result = await pipeline.run_once()
        await alert_collect_if_degraded(
            notifier=notifier,
            result=result,
            engine=engine,
            min_consecutive=3,
            cooldown_hours=6,
        )
    assert notifier.messages == [], "should not alert until 3rd consecutive failure"

    result = await pipeline.run_once()
    await alert_collect_if_degraded(
        notifier=notifier,
        result=result,
        engine=engine,
        min_consecutive=3,
        cooldown_hours=6,
    )
    assert len(notifier.messages) == 1
    assert "news_inserted=0" in notifier.messages[0]


@pytest.mark.asyncio
async def test_alert_resets_when_condition_clears(tmp_path: Path) -> None:
    """After a healthy cycle the consecutive counter resets."""
    engine = build_engine(tmp_path / "e2e6.db")
    init_schema(engine)

    bad_pipeline = CollectorPipeline(
        engine=engine,
        news_sources=[_StubNewsSource([])],
        calendar_sources=[],
        price_source=None,
        price_symbols=[],
    )
    healthy_news = [
        NormalizedNews(
            source="stub",
            external_id="ok",
            published_at=datetime.now(UTC),
            title="Hello",
            summary="x",
            url="https://x",
            keywords=[],
            raw_payload={},
        )
    ]
    good_pipeline = CollectorPipeline(
        engine=engine,
        news_sources=[_StubNewsSource(healthy_news)],
        calendar_sources=[],
        price_source=None,
        price_symbols=[],
    )

    notifier = _RecordingNotifier()
    # Two failures, then a success — counter should reset.
    for _ in range(2):
        await alert_collect_if_degraded(
            notifier=notifier,
            result=await bad_pipeline.run_once(),
            engine=engine,
            min_consecutive=3,
        )
    await alert_collect_if_degraded(
        notifier=notifier,
        result=await good_pipeline.run_once(),
        engine=engine,
        min_consecutive=3,
    )
    # Now two more failures should NOT trigger an alert (counter just reset).
    for _ in range(2):
        await alert_collect_if_degraded(
            notifier=notifier,
            result=await bad_pipeline.run_once(),
            engine=engine,
            min_consecutive=3,
        )
    assert notifier.messages == [], "counter should reset after a healthy cycle"
