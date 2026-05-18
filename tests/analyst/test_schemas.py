"""Tests for analyst schemas."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from ig_qt.analyst.schemas import (
    AngleDraft,
    RankedItem,
    RankerOutput,
    VisualSpec,
)


def test_ranker_output_validates() -> None:
    out = RankerOutput.model_validate(
        {
            "ranked": [
                {"id": 1, "score": 0.91, "reason": "Fed hawkish"},
                {"id": 2, "score": 0.5, "reason": "Minor data"},
            ]
        }
    )
    assert len(out.ranked) == 2
    assert out.ranked[0].score == 0.91


def test_ranker_score_must_be_in_range() -> None:
    with pytest.raises(ValidationError):
        RankedItem.model_validate({"id": 1, "score": 1.5, "reason": "x"})


def test_angle_draft_visual_spec_chart() -> None:
    draft = AngleDraft.model_validate(
        {
            "post_type": "feed",
            "topic_tag": "fed_hawkish",
            "angle": "Fed hawkish, USD/JPY watch",
            "key_points": ["a", "b", "c"],
            "caption_draft": "..." * 100,
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
    )
    assert isinstance(draft.visual_spec, VisualSpec)
    assert draft.visual_spec.type == "chart"
