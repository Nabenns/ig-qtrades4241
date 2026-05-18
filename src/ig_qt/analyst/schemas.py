"""Pydantic schemas for LLM structured output."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RankedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=400)


class RankerOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ranked: list[RankedItem] = Field(min_length=1, max_length=10)


class StatItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(min_length=1, max_length=32)
    value: str = Field(min_length=1, max_length=40)


class QuoteBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(min_length=10, max_length=280)
    attribution: str = Field(min_length=1, max_length=80)
    role: str | None = Field(default=None, max_length=120)


class InsightBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(min_length=2, max_length=48)
    body: str = Field(min_length=10, max_length=400)


class VisualSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["chart", "headline", "event", "recap", "big_number", "panel", "news_hero"]
    symbol: str | None = None
    timeframe: Literal["15m", "1h", "4H", "1D"] | None = None
    annotations: list[str] = Field(default_factory=list)
    headline: str = Field(min_length=1, max_length=200)
    subheadline: str | None = None

    # Hero "big number" for feed posts (e.g. price level, rate %, change %)
    big_number: str | None = Field(default=None, max_length=32)
    big_number_label: str | None = Field(default=None, max_length=64)
    big_number_caption: str | None = Field(default=None, max_length=120)

    # Mini stats strip (3-4 items max)
    stats: list[StatItem] = Field(default_factory=list, max_length=4)

    # Optional quote attribution
    quote: QuoteBlock | None = None

    # Optional insight highlight ("WHY THIS MATTERS" / "WHAT TO WATCH")
    insight: InsightBlock | None = None

    # Hero image generation prompt (for AI-generated dramatic background)
    hero_image_prompt: str | None = Field(default=None, max_length=400)
    # Highlight phrase + color (CW-style: phrase di-color contrast di headline)
    highlight_phrase: str | None = Field(default=None, max_length=80)
    highlight_color: Literal["green", "red", "amber", "teal"] | None = None

    @field_validator("annotations", mode="before")
    @classmethod
    def _coerce_annotations(cls, v: Any) -> list[str]:
        """Coerce null/None/missing → empty list (LLMs sometimes emit null)."""
        if v is None:
            return []
        return list(v) if not isinstance(v, list) else v

    @field_validator("stats", mode="before")
    @classmethod
    def _coerce_stats(cls, v: Any) -> list[Any]:
        if v is None:
            return []
        return list(v) if not isinstance(v, list) else v


class AngleDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    post_type: Literal["feed", "story"]
    topic_tag: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=64)
    angle: str = Field(min_length=4, max_length=240)
    key_points: list[str] = Field(min_length=1, max_length=8)
    caption_draft: str = Field(min_length=80, max_length=2200)
    visual_spec: VisualSpec
    disclaimer_required: bool
    confidence: float = Field(ge=0.0, le=1.0)
    # 3 dynamic hashtags tailored to this specific post topic
    # (composer will merge with brand-fixed hashtags)
    dynamic_hashtags: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("dynamic_hashtags", mode="before")
    @classmethod
    def _coerce_hashtags(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            return []
        # Normalize: ensure each tag starts with #, no spaces
        out: list[str] = []
        for raw in v:
            if not isinstance(raw, str):
                continue
            tag = raw.strip().replace(" ", "").lower()
            if not tag:
                continue
            if not tag.startswith("#"):
                tag = f"#{tag}"
            # Strip non-alphanumeric except # and underscore
            tag = "".join(ch for ch in tag if ch.isalnum() or ch in "#_")
            if len(tag) > 1:
                out.append(tag)
        return out[:5]
