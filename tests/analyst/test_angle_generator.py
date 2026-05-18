"""Tests for angle generator stage."""
from __future__ import annotations

import json
from typing import Any

import pytest

from ig_qt.analyst.angle_generator import generate_angle
from ig_qt.analyst.schemas import AngleDraft
from ig_qt.llm.base import LLMResponse

_VALID_PAYLOAD = {
    "post_type": "feed",
    "topic_tag": "fed_hawkish",
    "angle": "Fed hawkish, USD/JPY watch",
    "key_points": ["a", "b", "c"],
    "caption_draft": "x" * 200,
    "visual_spec": {
        "type": "chart",
        "symbol": "USD/JPY",
        "timeframe": "4H",
        "annotations": ["158", "160"],
        "headline": "USD/JPY at key levels",
    },
    "disclaimer_required": True,
    "confidence": 0.85,
}


class _FakeProvider:
    name = "fake"

    async def complete_json(self, **kwargs: Any) -> LLMResponse:
        return LLMResponse(
            content=json.dumps(_VALID_PAYLOAD),
            parsed=_VALID_PAYLOAD,
            model=kwargs["model"],
            input_tokens=200,
            output_tokens=400,
        )

    async def complete_text(self, **kwargs: Any) -> LLMResponse:  # pragma: no cover
        raise NotImplementedError


@pytest.mark.asyncio
async def test_generate_angle_returns_validated_draft() -> None:
    draft = await generate_angle(
        provider=_FakeProvider(),
        model="claude-sonnet",
        post_type="feed",
        selected_payload="some news context",
        prices=[],
        posted_topics=[],
    )
    assert isinstance(draft, AngleDraft)
    assert draft.confidence == 0.85
