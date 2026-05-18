"""Tests for ranker stage."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from ig_qt.analyst.ranker import build_ranker_input, run_ranker
from ig_qt.analyst.schemas import RankerOutput
from ig_qt.llm.base import LLMResponse


class _News:
    def __init__(self, rid: int, title: str) -> None:
        self.id = rid
        self.source = "newsapi"
        self.published_at = datetime(2026, 5, 17, 12, tzinfo=UTC)
        self.title = title
        self.summary: str | None = None


class _FakeProvider:
    name = "fake"

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.last_call: dict[str, Any] = {}

    async def complete_json(self, **kwargs: Any) -> LLMResponse:
        self.last_call = kwargs
        text = json.dumps(self._payload)
        return LLMResponse(
            content=text,
            parsed=self._payload,
            model=kwargs["model"],
            input_tokens=100,
            output_tokens=50,
        )

    async def complete_text(self, **kwargs: Any) -> LLMResponse:  # pragma: no cover
        raise NotImplementedError


def test_build_ranker_input_renders_lines() -> None:
    out = build_ranker_input(
        today=datetime(2026, 5, 17, tzinfo=UTC),
        news=[_News(1, "Fed Holds Rates"), _News(2, "ECB Cuts")],
        events=[],
        prices=[],
        posted_topics=["fed_hike", "ecb_cut"],
    )
    assert "Fed Holds Rates" in out
    assert "fed_hike" in out


@pytest.mark.asyncio
async def test_run_ranker_parses_response() -> None:
    provider = _FakeProvider({"ranked": [{"id": 1, "score": 0.9, "reason": "high impact"}]})
    result = await run_ranker(
        provider=provider,
        model="gemini-flash",
        today=datetime(2026, 5, 17, tzinfo=UTC),
        news=[_News(1, "Fed Holds")],
        events=[],
        prices=[],
        posted_topics=[],
    )
    assert isinstance(result, RankerOutput)
    assert result.ranked[0].id == 1


@pytest.mark.asyncio
async def test_run_ranker_retries_on_invalid_json() -> None:
    class FlakyProvider:
        name = "flaky"
        attempts = 0

        async def complete_json(self, **kwargs: Any) -> LLMResponse:
            FlakyProvider.attempts += 1
            if FlakyProvider.attempts == 1:
                return LLMResponse(
                    content="not json",
                    parsed=None,
                    model="m",
                    input_tokens=1,
                    output_tokens=1,
                )
            return LLMResponse(
                content='{"ranked":[{"id":1,"score":0.5,"reason":"x"}]}',
                parsed={"ranked": [{"id": 1, "score": 0.5, "reason": "x"}]},
                model="m",
                input_tokens=1,
                output_tokens=1,
            )

        async def complete_text(self, **kwargs: Any) -> LLMResponse:  # pragma: no cover
            raise NotImplementedError

    result = await run_ranker(
        provider=FlakyProvider(),  # type: ignore[arg-type]
        model="m",
        today=datetime(2026, 5, 17, tzinfo=UTC),
        news=[_News(1, "x")],
        events=[],
        prices=[],
        posted_topics=[],
    )
    assert result.ranked[0].id == 1
    assert FlakyProvider.attempts == 2
