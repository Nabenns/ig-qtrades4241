"""Tests for analyst runner."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from ig_qt.analyst.runner import AnalystRunner
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.llm.base import LLMResponse
from ig_qt.models import Event, EvergreenDraft, PostDraft, RawNews


class _MockProvider:
    name = "mock"

    def __init__(self, *, low_confidence: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self._low_confidence = low_confidence

    async def complete_json(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        sys = kwargs["system"]
        if "Rank" in sys or "ranked" in sys.lower():
            payload: dict[str, Any] = {
                "ranked": [
                    {"id": 1, "score": 0.9, "reason": "Fed major"},
                    {"id": 2, "score": 0.7, "reason": "ECB minor"},
                    {"id": 3, "score": 0.5, "reason": "CPI event"},
                ]
            }
        else:
            confidence = 0.3 if self._low_confidence else 0.85
            payload = {
                "post_type": "feed" if "feed" in kwargs["user"][:200] else "story",
                "topic_tag": "fed_hawkish",
                "angle": "Fed hawkish",
                "key_points": ["a", "b", "c"],
                "caption_draft": "x" * 200,
                "visual_spec": {
                    "type": "headline",
                    "headline": "Fed Hawkish",
                },
                "disclaimer_required": True,
                "confidence": confidence,
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


@pytest.fixture
def seeded_db(tmp_path: Path) -> Any:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    with session_scope(engine) as s:
        s.add(
            RawNews(
                source="newsapi",
                external_id="1",
                published_at=datetime.now(UTC),
                title="Fed Holds Rates Hawkish",
                summary="hot",
                url="https://x",
                keywords=[],
                raw_payload={},
                dedup_key="k1",
            )
        )
        s.add(
            RawNews(
                source="gnews",
                external_id="2",
                published_at=datetime.now(UTC),
                title="ECB Press",
                summary="meh",
                url="https://y",
                keywords=[],
                raw_payload={},
                dedup_key="k2",
            )
        )
        s.add(
            Event(
                source="ff",
                event_time=datetime(2026, 5, 18, 12, tzinfo=UTC),
                country="US",
                currency="USD",
                name="CPI",
                impact="high",
                forecast="0.3%",
                previous="0.4%",
                actual=None,
                dedup_key="e1",
            )
        )
        s.add(
            RawNews(
                source="newsapi",
                external_id="3",
                published_at=datetime.now(UTC),
                title="BOE Hold",
                summary="-",
                url="https://z",
                keywords=[],
                raw_payload={},
                dedup_key="k3",
            )
        )
    return engine


@pytest.mark.asyncio
async def test_runner_creates_drafts(seeded_db: Any) -> None:
    runner = AnalystRunner(
        engine=seeded_db,
        provider=_MockProvider(),
        ranker_model="r",
        composer_model="c",
        story_count=2,
        confidence_threshold=0.6,
    )
    summary = await runner.run_once(today=datetime(2026, 5, 17, tzinfo=UTC))
    assert summary.feed_drafts == 1
    assert summary.story_drafts == 2

    with session_scope(seeded_db) as s:
        drafts = s.query(PostDraft).all()
        assert len(drafts) == 3
        assert any(d.post_type == "feed" for d in drafts)
        assert all(d.status == "pending" for d in drafts)


@pytest.mark.asyncio
async def test_runner_falls_back_to_evergreen(seeded_db: Any) -> None:
    with session_scope(seeded_db) as s:
        s.add(
            EvergreenDraft(
                topic_tag="basics_001",
                angle="Forex basics",
                key_points=["a"],
                caption_draft="x" * 200,
                visual_spec={"type": "headline", "headline": "Basics"},
                disclaimer_required=True,
            )
        )

    runner = AnalystRunner(
        engine=seeded_db,
        provider=_MockProvider(low_confidence=True),
        ranker_model="r",
        composer_model="c",
        story_count=0,
        confidence_threshold=0.6,
    )
    summary = await runner.run_once(today=datetime(2026, 5, 17, tzinfo=UTC))
    assert summary.feed_drafts == 1
    assert summary.evergreen_used is True
