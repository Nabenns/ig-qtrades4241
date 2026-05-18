"""Pydantic schemas for LLM structured output."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RankedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=400)


class RankerOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ranked: list[RankedItem] = Field(min_length=1, max_length=10)


class VisualSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["chart", "headline", "event", "recap"]
    symbol: str | None = None
    timeframe: Literal["15m", "1h", "4H", "1D"] | None = None
    annotations: list[str] = Field(default_factory=list)
    headline: str = Field(min_length=1, max_length=120)
    subheadline: str | None = None


class AngleDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    post_type: Literal["feed", "story"]
    topic_tag: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=64)
    angle: str = Field(min_length=4, max_length=200)
    key_points: list[str] = Field(min_length=1, max_length=8)
    caption_draft: str = Field(min_length=80, max_length=2200)
    visual_spec: VisualSpec
    disclaimer_required: bool
    confidence: float = Field(ge=0.0, le=1.0)
