# M3 Analyst — Implementation Plan

> **Parent:** [`../2026-05-17-ig-forex-automation.md`](../2026-05-17-ig-forex-automation.md)
> **Prereq:** M1 + M2 complete.

**Goal:** Two-stage LLM pipeline that ranks 24h news + events into top picks, then generates structured `PostDraft` records (caption, key points, visual spec, confidence). Provides evergreen content fallback when all drafts score low. End state: `python -m ig_qt analyze --once` selects top news, generates 1 feed draft + up to 3 story drafts, persists them with `status='pending'`.

**Files created in M3:**
- `src/ig_qt/analyst/__init__.py`, `runner.py`, `ranker.py`, `angle_generator.py`, `evergreen.py`
- `src/ig_qt/analyst/prompts/ranker.v1.md`, `composer.v1.md`, `evergreen.v1.md`
- `src/ig_qt/analyst/schemas.py` (Pydantic schemas for LLM output)
- `tests/analyst/test_*.py`
- Modify: `src/ig_qt/app.py`, `src/ig_qt/__main__.py` (add `analyze` subcommand)

---

## Task 3.1: Pydantic schemas for LLM I/O

**Files:**
- Create: `src/ig_qt/analyst/__init__.py`
- Create: `src/ig_qt/analyst/schemas.py`
- Create: `tests/analyst/__init__.py`
- Create: `tests/analyst/test_schemas.py`

- [ ] **Step 1: Write failing test**

`tests/analyst/test_schemas.py`:

```python
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
```

- [ ] **Step 2: Implement `src/ig_qt/analyst/__init__.py`**

```python
"""LLM-driven content analysis."""
from __future__ import annotations

from ig_qt.analyst.schemas import AngleDraft, RankedItem, RankerOutput, VisualSpec

__all__ = ["AngleDraft", "RankedItem", "RankerOutput", "VisualSpec"]
```

- [ ] **Step 3: Implement `src/ig_qt/analyst/schemas.py`**

```python
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
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/analyst/test_schemas.py -v
uv run mypy --strict src/ig_qt/analyst/schemas.py
git add src/ig_qt/analyst/__init__.py src/ig_qt/analyst/schemas.py tests/analyst/__init__.py tests/analyst/test_schemas.py
git commit -m "feat(analyst): add Pydantic schemas for LLM structured output"
```

---

## Task 3.2: Prompt templates (versioned)

**Files:**
- Create: `src/ig_qt/analyst/prompts/__init__.py`
- Create: `src/ig_qt/analyst/prompts/ranker.v1.md`
- Create: `src/ig_qt/analyst/prompts/composer.v1.md`
- Create: `src/ig_qt/analyst/prompts/evergreen.v1.md`
- Create: `src/ig_qt/analyst/prompts/loader.py`
- Create: `tests/analyst/test_prompts.py`

- [ ] **Step 1: Create `src/ig_qt/analyst/prompts/__init__.py`**

Empty file.

- [ ] **Step 2: Create `ranker.v1.md`**

````markdown
# Ranker prompt v1

## System

You are a financial news editor for an Indonesian Instagram account focused on forex and macroeconomics. Rank candidate news + events by their relevance for today's content.

Scoring criteria (apply in order, return one float 0.0-1.0):
1. Impact on major FX pairs (USD, EUR, JPY, GBP, gold) — high impact = +0.4.
2. Recency — published within last 12h = +0.3, 12-24h = +0.15.
3. Diversity vs already-posted topics — already-covered topic in last 7 days = -0.4.
4. Avoid duplicate angles within ranked set — if 5 items are about the same Fed event, pick only the most impactful.

Constraints:
- Return strictly valid JSON. No markdown fences. No commentary.
- Schema: `{"ranked": [{"id": int, "score": float, "reason": "string ≤200 chars"}, ...]}`.
- Return at most 10 items, sorted by score descending.

## User template

Today (Asia/Jakarta): {today}

Already posted topics (last 7 days):
{posted_topics}

Candidate news (id | source | published_at | title | summary):
{news_lines}

Upcoming high/medium-impact events (next 24h):
{events_lines}

Snapshot prices (D1 close):
{prices_lines}

Return the JSON object.
````

- [ ] **Step 3: Create `composer.v1.md`**

````markdown
# Composer prompt v1

## System

You are a content writer for an Indonesian Instagram account focused on forex and macroeconomics. Write a caption draft for ONE post based on the provided news/event context.

Rules:
- Language: Indonesian, casual-professional. Mix English technical terms (FOMC, hawkish, dovish, breakout) — do not translate.
- Tone: education and market context. NEVER write "BUY/SELL", "pasti naik/turun", "guaranteed profit", or trading signals.
- Length: 1500-2000 chars caption_draft (excluding hashtags — caller appends).
- If the post is directional (mentions price target, breakout, or pair direction), set `disclaimer_required=true`.
- All numbers must come from the provided prices/events. Do NOT invent figures. If a number isn't provided, omit it.
- Return strictly valid JSON matching the schema. No markdown fences.

Schema:
```
{
  "post_type": "feed" | "story",
  "topic_tag": "snake_case_short",
  "angle": "1-line angle description",
  "key_points": ["3-5 bullet points"],
  "caption_draft": "...",
  "visual_spec": {
    "type": "chart" | "headline" | "event",
    "symbol": "EUR/USD" | null,
    "timeframe": "1h" | "4H" | "1D" | null,
    "annotations": ["short labels for chart S/R lines"],
    "headline": "1-line for image",
    "subheadline": "optional"
  },
  "disclaimer_required": true | false,
  "confidence": 0.0-1.0
}
```

`confidence`:
- 0.9+ : strong news with clear angle and supporting price data
- 0.7-0.9 : decent news with reasonable angle
- 0.5-0.7 : weak source data, generic angle
- below 0.5 : reject — caller will fall back to evergreen

## User template

Post type: {post_type}

Selected news/event:
{selected_payload}

Available price snapshots:
{prices_lines}

Recently posted topics to avoid repeating angle:
{posted_topics}

Return the JSON object.
````

- [ ] **Step 4: Create `evergreen.v1.md`**

````markdown
# Evergreen pool prompt v1

## System

Generate evergreen forex/finance educational posts in Indonesian for an Instagram account. These run when no fresh news is available. They must NOT reference current prices, dates, or events.

Rules:
- Language: Indonesian casual-professional, English technical terms preserved.
- Topics: forex basics, risk management, trading psychology, macroeconomic concepts (CPI, NFP explainer, central bank roles), chart pattern education.
- Tone: education, NEVER trading signal.
- Each post must include `disclaimer_required=true` for directional/educational posts that reference market behavior.
- Caption 1200-2000 chars.

Return JSON array of 10 AngleDraft objects matching the composer schema, all `post_type="feed"`, all `visual_spec.type="headline"`, `confidence=0.7` for all.

## User template

Generate 10 distinct evergreen posts. Topics should not overlap.
````

- [ ] **Step 5: Implement `src/ig_qt/analyst/prompts/loader.py`**

```python
"""Prompt template loader."""
from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


class PromptTemplate:
    """A parsed prompt with `system` and `user` sections."""

    def __init__(self, *, version: str, system: str, user: str) -> None:
        self.version = version
        self.system = system
        self.user_template = user

    def render_user(self, **kwargs: object) -> str:
        return self.user_template.format(**kwargs)


def _split_sections(text: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        name = m.group(1).strip().lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts[name] = text[start:end].strip()
    return parts


def load_prompt(name: str) -> PromptTemplate:
    """Load `<name>.md` from prompts/ directory by package resource."""
    pkg = "ig_qt.analyst.prompts"
    res = resources.files(pkg).joinpath(f"{name}.md")
    raw = Path(str(res)).read_text(encoding="utf-8")
    sections = _split_sections(raw)
    if "system" not in sections or "user template" not in sections:
        raise ValueError(f"prompt {name} missing required sections")
    return PromptTemplate(
        version=name, system=sections["system"], user=sections["user template"]
    )
```

- [ ] **Step 6: Update `pyproject.toml` to ship prompts as package data**

In `[tool.hatch.build.targets.wheel]`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/ig_qt"]

[tool.hatch.build.targets.wheel.force-include]
"src/ig_qt/analyst/prompts/ranker.v1.md" = "ig_qt/analyst/prompts/ranker.v1.md"
"src/ig_qt/analyst/prompts/composer.v1.md" = "ig_qt/analyst/prompts/composer.v1.md"
"src/ig_qt/analyst/prompts/evergreen.v1.md" = "ig_qt/analyst/prompts/evergreen.v1.md"
```

- [ ] **Step 7: Write test**

`tests/analyst/test_prompts.py`:

```python
"""Tests for prompt loader."""
from __future__ import annotations

from ig_qt.analyst.prompts.loader import load_prompt


def test_load_ranker_prompt() -> None:
    p = load_prompt("ranker.v1")
    assert "JSON" in p.system
    assert "{news_lines}" in p.user_template
    rendered = p.render_user(
        today="2026-05-17",
        posted_topics="-",
        news_lines="1 | newsapi | 12:00 | Fed Holds | summary",
        events_lines="-",
        prices_lines="-",
    )
    assert "Fed Holds" in rendered


def test_load_composer_prompt() -> None:
    p = load_prompt("composer.v1")
    assert "Indonesian" in p.system
    assert "{selected_payload}" in p.user_template
```

- [ ] **Step 8: Run + commit**

```bash
uv run sync       # if pyproject changed
uv run pytest tests/analyst/test_prompts.py -v
uv run mypy --strict src/ig_qt/analyst/prompts/
git add src/ig_qt/analyst/prompts/ pyproject.toml tests/analyst/test_prompts.py
git commit -m "feat(analyst): add versioned prompt templates and loader"
```

---

## Task 3.3: Ranker stage

**Files:**
- Create: `src/ig_qt/analyst/ranker.py`
- Create: `tests/analyst/test_ranker.py`

- [ ] **Step 1: Write failing test**

`tests/analyst/test_ranker.py`:

```python
"""Tests for ranker stage."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from ig_qt.analyst.ranker import build_ranker_input, run_ranker
from ig_qt.analyst.schemas import RankerOutput
from ig_qt.llm.base import LLMResponse


def _news_row(rid: int, title: str) -> Any:
    class N:
        id = rid
        source = "newsapi"
        published_at = datetime(2026, 5, 17, 12, tzinfo=timezone.utc)
    N.title = title
    N.summary = None
    return N


class _FakeProvider:
    name = "fake"

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.last_call: dict[str, Any] = {}

    async def complete_json(self, **kwargs: Any) -> LLMResponse:
        self.last_call = kwargs
        import json
        text = json.dumps(self._payload)
        return LLMResponse(
            content=text, parsed=self._payload, model=kwargs["model"],
            input_tokens=100, output_tokens=50,
        )


def test_build_ranker_input_renders_lines() -> None:
    out = build_ranker_input(
        today=datetime(2026, 5, 17, tzinfo=timezone.utc),
        news=[_news_row(1, "Fed Holds Rates"), _news_row(2, "ECB Cuts")],
        events=[],
        prices=[],
        posted_topics=["fed_hike", "ecb_cut"],
    )
    assert "Fed Holds Rates" in out
    assert "fed_hike" in out


@pytest.mark.asyncio
async def test_run_ranker_parses_response() -> None:
    provider = _FakeProvider(
        {"ranked": [{"id": 1, "score": 0.9, "reason": "high impact"}]}
    )
    result = await run_ranker(
        provider=provider,
        model="gemini-flash",
        today=datetime(2026, 5, 17, tzinfo=timezone.utc),
        news=[_news_row(1, "Fed Holds")],
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
                    content="not json", parsed=None, model="m",
                    input_tokens=1, output_tokens=1,
                )
            return LLMResponse(
                content='{"ranked":[{"id":1,"score":0.5,"reason":"x"}]}',
                parsed={"ranked": [{"id": 1, "score": 0.5, "reason": "x"}]},
                model="m", input_tokens=1, output_tokens=1,
            )

    result = await run_ranker(
        provider=FlakyProvider(),  # type: ignore[arg-type]
        model="m",
        today=datetime(2026, 5, 17, tzinfo=timezone.utc),
        news=[_news_row(1, "x")],
        events=[],
        prices=[],
        posted_topics=[],
    )
    assert result.ranked[0].id == 1
    assert FlakyProvider.attempts == 2
```

- [ ] **Step 2: Implement `src/ig_qt/analyst/ranker.py`**

```python
"""Stage 1: rank news + events by relevance."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from loguru import logger
from pydantic import ValidationError

from ig_qt.analyst.prompts.loader import load_prompt
from ig_qt.analyst.schemas import RankerOutput
from ig_qt.llm.base import LLMProvider


class _NewsRow(Protocol):
    id: int
    source: str
    published_at: datetime | None
    title: str
    summary: str | None


class _EventRow(Protocol):
    id: int
    event_time: datetime
    currency: str | None
    name: str
    impact: str
    forecast: str | None


class _PriceRow(Protocol):
    symbol: str
    ohlc: list[dict[str, Any]]


def build_ranker_input(
    *,
    today: datetime,
    news: Sequence[_NewsRow],
    events: Sequence[_EventRow],
    prices: Sequence[_PriceRow],
    posted_topics: Sequence[str],
) -> str:
    p = load_prompt("ranker.v1")

    def _news_line(n: _NewsRow) -> str:
        ts = n.published_at.isoformat() if n.published_at else "-"
        return f"{n.id} | {n.source} | {ts} | {n.title} | {n.summary or ''}"[:500]

    def _event_line(e: _EventRow) -> str:
        return (
            f"{e.id} | {e.event_time.isoformat()} | {e.currency or '-'} | "
            f"{e.impact} | {e.name} | forecast={e.forecast or '-'}"
        )[:400]

    def _price_line(pr: _PriceRow) -> str:
        if not pr.ohlc:
            return f"{pr.symbol} | no data"
        last = pr.ohlc[-1]
        return f"{pr.symbol} | close={last['close']} t={last['t']}"

    return p.render_user(
        today=today.date().isoformat(),
        posted_topics="\n".join(f"- {t}" for t in posted_topics) or "(none)",
        news_lines="\n".join(_news_line(n) for n in news) or "(none)",
        events_lines="\n".join(_event_line(e) for e in events) or "(none)",
        prices_lines="\n".join(_price_line(p) for p in prices) or "(none)",
    )


async def run_ranker(
    *,
    provider: LLMProvider,
    model: str,
    today: datetime,
    news: Sequence[_NewsRow],
    events: Sequence[_EventRow],
    prices: Sequence[_PriceRow],
    posted_topics: Sequence[str],
    max_attempts: int = 2,
) -> RankerOutput:
    p = load_prompt("ranker.v1")
    user = build_ranker_input(
        today=today, news=news, events=events, prices=prices, posted_topics=posted_topics
    )

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await provider.complete_json(
                system=p.system, user=user, model=model,
                temperature=0.2, max_output_tokens=1500,
            )
            if resp.parsed is None:
                raise ValueError("ranker returned non-JSON content")
            output = RankerOutput.model_validate(resp.parsed)
            logger.info(
                "ranker_ok attempt={} count={} input_tokens={} output_tokens={}",
                attempt, len(output.ranked), resp.input_tokens, resp.output_tokens,
            )
            return output
        except (ValidationError, ValueError) as exc:
            last_error = exc
            logger.warning("ranker_retry attempt={} error={}", attempt, exc)
    raise RuntimeError(f"ranker failed after {max_attempts} attempts: {last_error}")
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/analyst/test_ranker.py -v
uv run mypy --strict src/ig_qt/analyst/ranker.py
git add src/ig_qt/analyst/ranker.py tests/analyst/test_ranker.py
git commit -m "feat(analyst): add stage 1 ranker"
```

---

## Task 3.4: Angle generator stage

**Files:**
- Create: `src/ig_qt/analyst/angle_generator.py`
- Create: `tests/analyst/test_angle_generator.py`

- [ ] **Step 1: Write failing test**

`tests/analyst/test_angle_generator.py`:

```python
"""Tests for angle generator stage."""
from __future__ import annotations

import json
from datetime import datetime, timezone
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
```

- [ ] **Step 2: Implement `src/ig_qt/analyst/angle_generator.py`**

```python
"""Stage 2: generate full caption + visual_spec for a selected item."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, Protocol

from loguru import logger
from pydantic import ValidationError

from ig_qt.analyst.prompts.loader import load_prompt
from ig_qt.analyst.schemas import AngleDraft
from ig_qt.llm.base import LLMProvider


class _PriceRow(Protocol):
    symbol: str
    ohlc: list[dict[str, Any]]


async def generate_angle(
    *,
    provider: LLMProvider,
    model: str,
    post_type: Literal["feed", "story"],
    selected_payload: str,
    prices: Sequence[_PriceRow],
    posted_topics: Sequence[str],
    max_attempts: int = 2,
) -> AngleDraft:
    p = load_prompt("composer.v1")

    def _price_line(pr: _PriceRow) -> str:
        if not pr.ohlc:
            return f"{pr.symbol} | no data"
        last = pr.ohlc[-1]
        return f"{pr.symbol} | close={last['close']} t={last['t']}"

    user = p.render_user(
        post_type=post_type,
        selected_payload=selected_payload,
        prices_lines="\n".join(_price_line(p) for p in prices) or "(none)",
        posted_topics="\n".join(f"- {t}" for t in posted_topics) or "(none)",
    )

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await provider.complete_json(
                system=p.system, user=user, model=model,
                temperature=0.6, max_output_tokens=2500,
            )
            if resp.parsed is None:
                raise ValueError("angle generator returned non-JSON")
            draft = AngleDraft.model_validate(resp.parsed)
            if draft.post_type != post_type:
                raise ValueError(f"post_type mismatch: expected {post_type}, got {draft.post_type}")
            logger.info(
                "angle_ok post_type={} topic={} confidence={} tokens_in={} tokens_out={}",
                draft.post_type, draft.topic_tag, draft.confidence,
                resp.input_tokens, resp.output_tokens,
            )
            return draft
        except (ValidationError, ValueError) as exc:
            last_error = exc
            logger.warning("angle_retry attempt={} error={}", attempt, exc)
    raise RuntimeError(f"angle gen failed after {max_attempts} attempts: {last_error}")
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/analyst/test_angle_generator.py -v
uv run mypy --strict src/ig_qt/analyst/angle_generator.py
git add src/ig_qt/analyst/angle_generator.py tests/analyst/test_angle_generator.py
git commit -m "feat(analyst): add stage 2 angle generator"
```

---

## Task 3.5: Evergreen content pool generator

**Files:**
- Create: `src/ig_qt/analyst/evergreen.py`
- Create: `tests/analyst/test_evergreen.py`
- Create: `scripts/generate_evergreen.py`

**Depends on:** OD-1 (9router availability) — `scripts/generate_evergreen.py` requires real LLM access; unit tests use stub.

- [ ] **Step 1: Add `evergreen_drafts` table to models**

In `src/ig_qt/models.py`, append after `PostedTopic`:

```python
class EvergreenDraft(Base):
    __tablename__ = "evergreen_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_tag: Mapped[str] = mapped_column(String(128), index=True)
    angle: Mapped[str] = mapped_column(Text)
    key_points: Mapped[list[Any]] = mapped_column(JSON)
    caption_draft: Mapped[str] = mapped_column(Text)
    visual_spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    disclaimer_required: Mapped[bool] = mapped_column(Boolean, default=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
```

- [ ] **Step 2: Write failing test**

`tests/analyst/test_evergreen.py`:

```python
"""Tests for evergreen pool."""
from __future__ import annotations

from pathlib import Path

from ig_qt.analyst.evergreen import pick_evergreen_draft, store_evergreen_drafts
from ig_qt.analyst.schemas import AngleDraft, VisualSpec
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import EvergreenDraft
from sqlalchemy import select


def _draft(tag: str) -> AngleDraft:
    return AngleDraft(
        post_type="feed",
        topic_tag=tag,
        angle="Edukasi forex basics",
        key_points=["a", "b"],
        caption_draft="x" * 200,
        visual_spec=VisualSpec(type="headline", headline="hello"),
        disclaimer_required=True,
        confidence=0.7,
    )


def test_store_and_pick_evergreen(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    drafts = [_draft(f"topic_{i}") for i in range(3)]
    with session_scope(engine) as s:
        store_evergreen_drafts(s, drafts)
    with session_scope(engine) as s:
        rows = s.execute(select(EvergreenDraft)).scalars().all()
        assert len(rows) == 3

    # Pick least-recently-used
    with session_scope(engine) as s:
        first = pick_evergreen_draft(s)
        assert first is not None
        assert first.used_count == 1
    with session_scope(engine) as s:
        second = pick_evergreen_draft(s)
        assert second is not None
        assert second.topic_tag != first.topic_tag
```

- [ ] **Step 3: Implement `src/ig_qt/analyst/evergreen.py`**

```python
"""Evergreen content pool: pre-generated educational drafts for dry days."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import asc
from sqlalchemy.orm import Session

from ig_qt.analyst.schemas import AngleDraft
from ig_qt.models import EvergreenDraft


def store_evergreen_drafts(session: Session, drafts: Sequence[AngleDraft]) -> int:
    """Insert generated evergreen drafts. Returns count inserted."""
    for d in drafts:
        session.add(
            EvergreenDraft(
                topic_tag=d.topic_tag,
                angle=d.angle,
                key_points=list(d.key_points),
                caption_draft=d.caption_draft,
                visual_spec=d.visual_spec.model_dump(),
                disclaimer_required=d.disclaimer_required,
            )
        )
    logger.info("evergreen_stored count={}", len(drafts))
    return len(drafts)


def pick_evergreen_draft(session: Session) -> EvergreenDraft | None:
    """Pick the least-recently-used evergreen draft and mark it used."""
    row = (
        session.query(EvergreenDraft)
        .order_by(asc(EvergreenDraft.last_used_at).nulls_first(), asc(EvergreenDraft.used_count))
        .first()
    )
    if row is None:
        return None
    row.used_count += 1
    row.last_used_at = datetime.now(timezone.utc)
    session.flush()
    logger.info("evergreen_picked id={} topic={}", row.id, row.topic_tag)
    return row
```

- [ ] **Step 4: Implement one-shot script `scripts/generate_evergreen.py`**

```python
"""One-time: batch-generate ~10 evergreen drafts via LLM. Run manually."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from loguru import logger
from pydantic import TypeAdapter

from ig_qt.analyst.evergreen import store_evergreen_drafts
from ig_qt.analyst.prompts.loader import load_prompt
from ig_qt.analyst.schemas import AngleDraft
from ig_qt.config import load_config
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.llm.factory import build_llm_provider
from ig_qt.logging_setup import configure_logging


async def _main() -> int:
    cfg = load_config(Path("config.yaml"))
    configure_logging(log_dir=cfg.paths.data_dir / "logs", level="INFO", json_logs=False)
    engine = build_engine(cfg.paths.data_dir / "ig_qt.db")
    init_schema(engine)
    provider = build_llm_provider(cfg.llm)
    p = load_prompt("evergreen.v1")
    resp = await provider.complete_json(
        system=p.system,
        user=p.render_user(),
        model=cfg.llm.composer_model,
        temperature=0.7,
        max_output_tokens=8000,
    )
    if resp.parsed is None:
        # Some providers wrap arrays in a key; try common shapes.
        try:
            resp_obj = json.loads(resp.content)
        except json.JSONDecodeError:
            logger.error("evergreen_llm_invalid_json")
            return 1
    else:
        resp_obj = resp.parsed
    items = resp_obj.get("drafts") if isinstance(resp_obj, dict) else resp_obj
    drafts = TypeAdapter(list[AngleDraft]).validate_python(items)
    with session_scope(engine) as s:
        store_evergreen_drafts(s, drafts)
    logger.info("evergreen_generated count={}", len(drafts))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
```

- [ ] **Step 5: Run + commit**

```bash
uv run pytest tests/analyst/test_evergreen.py -v
uv run mypy --strict src/ig_qt/analyst/evergreen.py scripts/generate_evergreen.py
git add src/ig_qt/models.py src/ig_qt/analyst/evergreen.py scripts/generate_evergreen.py tests/analyst/test_evergreen.py
git commit -m "feat(analyst): add evergreen content pool + one-shot generator script"
```

---

## Task 3.6: Analyst runner (orchestrate ranker + angle generator + persist)

**Files:**
- Create: `src/ig_qt/analyst/runner.py`
- Modify: `src/ig_qt/app.py`, `src/ig_qt/__main__.py`
- Create: `tests/analyst/test_runner.py`

- [ ] **Step 1: Write failing test**

`tests/analyst/test_runner.py`:

```python
"""Tests for analyst runner."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from ig_qt.analyst.runner import AnalystRunner
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.llm.base import LLMResponse
from ig_qt.models import EvergreenDraft, Event, PostDraft, PostedTopic, PriceCache, RawNews


class _MockProvider:
    name = "mock"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete_json(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        # Decide payload by prompt content
        if "Rank candidate" in kwargs["system"] or "ranked" in kwargs["system"]:
            payload: dict[str, Any] = {
                "ranked": [
                    {"id": 1, "score": 0.9, "reason": "Fed major"},
                    {"id": 2, "score": 0.7, "reason": "ECB minor"},
                ]
            }
        else:
            payload = {
                "post_type": kwargs.get("_post_type", "feed"),
                "topic_tag": "fed_hawkish",
                "angle": "Fed hawkish",
                "key_points": ["a", "b", "c"],
                "caption_draft": "x" * 200,
                "visual_spec": {
                    "type": "headline",
                    "headline": "Fed Hawkish",
                },
                "disclaimer_required": True,
                "confidence": 0.85,
            }
        return LLMResponse(
            content=json.dumps(payload),
            parsed=payload,
            model=kwargs["model"],
            input_tokens=100,
            output_tokens=200,
        )


@pytest.fixture
def seeded_db(tmp_path: Path):  # type: ignore[no-untyped-def]
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    with session_scope(engine) as s:
        s.add(
            RawNews(
                source="newsapi",
                external_id="1",
                published_at=datetime.now(timezone.utc),
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
                published_at=datetime.now(timezone.utc),
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
                event_time=datetime(2026, 5, 18, 12, tzinfo=timezone.utc),
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
    summary = await runner.run_once(today=datetime(2026, 5, 17, tzinfo=timezone.utc))
    assert summary.feed_drafts == 1
    assert summary.story_drafts == 2

    with session_scope(seeded_db) as s:
        drafts = s.query(PostDraft).all()
        assert len(drafts) == 3
        assert any(d.post_type == "feed" for d in drafts)
        assert all(d.status == "pending" for d in drafts)


@pytest.mark.asyncio
async def test_runner_falls_back_to_evergreen(seeded_db: Any, tmp_path: Path) -> None:
    # Seed an evergreen draft
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

    class LowConfidence(_MockProvider):
        async def complete_json(self, **kwargs: Any) -> LLMResponse:
            resp = await super().complete_json(**kwargs)
            if resp.parsed and "confidence" in resp.parsed:
                resp.parsed["confidence"] = 0.3  # type: ignore[index]
                resp = LLMResponse(
                    content=json.dumps(resp.parsed),
                    parsed=resp.parsed,
                    model=resp.model,
                    input_tokens=resp.input_tokens,
                    output_tokens=resp.output_tokens,
                )
            return resp

    runner = AnalystRunner(
        engine=seeded_db,
        provider=LowConfidence(),
        ranker_model="r",
        composer_model="c",
        story_count=0,
        confidence_threshold=0.6,
    )
    summary = await runner.run_once(today=datetime(2026, 5, 17, tzinfo=timezone.utc))
    assert summary.feed_drafts == 1
    assert summary.evergreen_used is True
```

- [ ] **Step 2: Implement `src/ig_qt/analyst/runner.py`**

```python
"""End-to-end analyst pipeline."""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from sqlalchemy import Engine, desc, select

from ig_qt.analyst.angle_generator import generate_angle
from ig_qt.analyst.evergreen import pick_evergreen_draft
from ig_qt.analyst.ranker import run_ranker
from ig_qt.analyst.schemas import AngleDraft, RankedItem, RankerOutput, VisualSpec
from ig_qt.db import session_scope
from ig_qt.llm.base import LLMProvider
from ig_qt.models import Event, PostDraft, PostedTopic, PriceCache, RawNews


@dataclass(frozen=True, slots=True)
class AnalystSummary:
    feed_drafts: int
    story_drafts: int
    evergreen_used: bool
    rejected_low_confidence: int


class AnalystRunner:
    def __init__(
        self,
        *,
        engine: Engine,
        provider: LLMProvider,
        ranker_model: str,
        composer_model: str,
        story_count: int = 3,
        confidence_threshold: float = 0.6,
        prompt_version: str = "ranker.v1+composer.v1",
    ) -> None:
        self._engine = engine
        self._provider = provider
        self._ranker_model = ranker_model
        self._composer_model = composer_model
        self._story_count = story_count
        self._threshold = confidence_threshold
        self._prompt_version = prompt_version

    def _load_news(self, session: Any, since: datetime) -> Sequence[RawNews]:
        return list(
            session.execute(
                select(RawNews)
                .where(RawNews.published_at >= since)
                .order_by(desc(RawNews.published_at))
                .limit(30)
            ).scalars()
        )

    def _load_events(self, session: Any, until: datetime) -> Sequence[Event]:
        return list(
            session.execute(
                select(Event)
                .where(Event.event_time <= until, Event.impact.in_(["high", "medium"]))
                .order_by(Event.event_time)
                .limit(20)
            ).scalars()
        )

    def _load_prices(self, session: Any) -> Sequence[Any]:
        # Latest cached snapshot per symbol
        rows = list(session.execute(select(PriceCache)).scalars())
        latest: dict[str, PriceCache] = {}
        for r in rows:
            cur = latest.get(r.symbol)
            if cur is None or r.fetched_at > cur.fetched_at:
                latest[r.symbol] = r
        return list(latest.values())

    def _load_posted_topics(self, session: Any, days: int = 7) -> Sequence[str]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return list(
            session.execute(
                select(PostedTopic.topic_tag).where(PostedTopic.last_posted_at >= cutoff)
            ).scalars()
        )

    def _serialize_payload_for_id(
        self, news: Sequence[RawNews], events: Sequence[Event], rid: int
    ) -> str:
        for n in news:
            if n.id == rid:
                return json.dumps(
                    {
                        "type": "news",
                        "title": n.title,
                        "summary": n.summary,
                        "url": n.url,
                        "published_at": (
                            n.published_at.isoformat() if n.published_at else None
                        ),
                        "source": n.source,
                    },
                    ensure_ascii=False,
                )
        for e in events:
            if e.id == rid:
                return json.dumps(
                    {
                        "type": "event",
                        "name": e.name,
                        "currency": e.currency,
                        "impact": e.impact,
                        "forecast": e.forecast,
                        "previous": e.previous,
                        "event_time": e.event_time.isoformat(),
                    },
                    ensure_ascii=False,
                )
        raise KeyError(f"id {rid} not found in news or events")

    def _persist_draft(
        self,
        session: Any,
        draft: AngleDraft,
        source_news_ids: list[int],
    ) -> None:
        session.add(
            PostDraft(
                post_type=draft.post_type,
                source_news_ids=source_news_ids,
                topic_tag=draft.topic_tag,
                angle=draft.angle,
                key_points=list(draft.key_points),
                caption_draft=draft.caption_draft,
                visual_spec=draft.visual_spec.model_dump(),
                disclaimer_required=draft.disclaimer_required,
                confidence=draft.confidence,
                llm_provider=self._provider.name,
                llm_model=self._composer_model,
                prompt_version=self._prompt_version,
                status="pending",
            )
        )

    def _persist_evergreen_as_draft(self, session: Any, ev: Any) -> None:
        spec = VisualSpec.model_validate(ev.visual_spec)
        session.add(
            PostDraft(
                post_type="feed",
                source_news_ids=[],
                topic_tag=f"evergreen_{ev.topic_tag}",
                angle=ev.angle,
                key_points=list(ev.key_points),
                caption_draft=ev.caption_draft,
                visual_spec=spec.model_dump(),
                disclaimer_required=ev.disclaimer_required,
                confidence=0.7,
                llm_provider="evergreen",
                llm_model="cached",
                prompt_version="evergreen.v1",
                status="pending",
            )
        )

    async def run_once(self, *, today: datetime) -> AnalystSummary:
        since = today - timedelta(hours=24)
        until = today + timedelta(hours=24)

        with session_scope(self._engine) as s:
            news = self._load_news(s, since)
            events = self._load_events(s, until)
            prices = self._load_prices(s)
            posted_topics = self._load_posted_topics(s)

        if not news and not events:
            logger.warning("analyst_no_inputs falling back to evergreen")
            return await self._fallback_evergreen(feed_only=True)

        rank: RankerOutput = await run_ranker(
            provider=self._provider,
            model=self._ranker_model,
            today=today,
            news=news,
            events=events,
            prices=prices,
            posted_topics=posted_topics,
        )
        if not rank.ranked:
            return await self._fallback_evergreen(feed_only=True)

        # Pick top-1 for feed, next N for story
        ranked_sorted = sorted(rank.ranked, key=lambda r: r.score, reverse=True)
        feed_pick = ranked_sorted[0]
        story_picks = ranked_sorted[1 : 1 + self._story_count]

        feed_drafts = 0
        story_drafts = 0
        rejected = 0
        evergreen_used = False

        with session_scope(self._engine) as s:
            payload = self._serialize_payload_for_id(news, events, feed_pick.id)
            try:
                feed_draft = await generate_angle(
                    provider=self._provider, model=self._composer_model,
                    post_type="feed",
                    selected_payload=payload,
                    prices=prices, posted_topics=posted_topics,
                )
                if feed_draft.confidence >= self._threshold:
                    self._persist_draft(s, feed_draft, [feed_pick.id])
                    feed_drafts = 1
                else:
                    rejected += 1
                    ev = pick_evergreen_draft(s)
                    if ev is not None:
                        self._persist_evergreen_as_draft(s, ev)
                        evergreen_used = True
                        feed_drafts = 1
            except Exception as exc:
                logger.warning("analyst_feed_gen_failed error={}", exc)
                ev = pick_evergreen_draft(s)
                if ev is not None:
                    self._persist_evergreen_as_draft(s, ev)
                    evergreen_used = True
                    feed_drafts = 1

            for pick in story_picks:
                try:
                    payload = self._serialize_payload_for_id(news, events, pick.id)
                    story_draft = await generate_angle(
                        provider=self._provider, model=self._composer_model,
                        post_type="story",
                        selected_payload=payload,
                        prices=prices, posted_topics=posted_topics,
                    )
                    if story_draft.confidence >= self._threshold:
                        self._persist_draft(s, story_draft, [pick.id])
                        story_drafts += 1
                    else:
                        rejected += 1
                except Exception as exc:
                    logger.warning("analyst_story_gen_failed error={}", exc)

        return AnalystSummary(
            feed_drafts=feed_drafts,
            story_drafts=story_drafts,
            evergreen_used=evergreen_used,
            rejected_low_confidence=rejected,
        )

    async def _fallback_evergreen(self, *, feed_only: bool) -> AnalystSummary:
        with session_scope(self._engine) as s:
            ev = pick_evergreen_draft(s)
            if ev is None:
                logger.error("analyst_dry_day_no_evergreen")
                return AnalystSummary(0, 0, False, 0)
            self._persist_evergreen_as_draft(s, ev)
        return AnalystSummary(feed_drafts=1, story_drafts=0, evergreen_used=True, rejected_low_confidence=0)
```

- [ ] **Step 3: Wire `analyze` subcommand**

In `src/ig_qt/app.py`, append:

```python
async def run_analyze_once(*, config_path: Path) -> int:
    from datetime import datetime, timezone

    from ig_qt.analyst.runner import AnalystRunner

    cfg = load_config(config_path)
    log_dir = cfg.paths.data_dir / "logs"
    configure_logging(log_dir=log_dir, level="INFO", json_logs=True)
    db_path = cfg.paths.data_dir / "ig_qt.db"
    engine = build_engine(db_path)
    init_schema(engine)
    provider = build_llm_provider(cfg.llm)
    runner = AnalystRunner(
        engine=engine,
        provider=provider,
        ranker_model=cfg.llm.ranker_model,
        composer_model=cfg.llm.composer_model,
        story_count=3,
        confidence_threshold=0.6,
    )
    summary = await runner.run_once(today=datetime.now(timezone.utc))
    logger.info(
        "analyze_done feed={} story={} evergreen={} rejected={}",
        summary.feed_drafts, summary.story_drafts,
        summary.evergreen_used, summary.rejected_low_confidence,
    )
    return 0 if (summary.feed_drafts + summary.story_drafts) > 0 else 2
```

In `src/ig_qt/__main__.py`, add `analyze` subcommand:

```python
sub.add_parser("analyze", help="Run analyst once")
```

And in dispatch:

```python
if args.cmd == "analyze":
    return asyncio.run(run_analyze_once(config_path=args.config))
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/analyst -v
uv run mypy --strict src/ig_qt/analyst/ src/ig_qt/app.py src/ig_qt/__main__.py
uv run ruff check src/ tests/
git add src/ig_qt/analyst/runner.py src/ig_qt/app.py src/ig_qt/__main__.py tests/analyst/test_runner.py
git commit -m "feat(analyst): orchestrate ranker+angle generator+evergreen fallback"
```

---

## M3 Acceptance Criteria

- [ ] All `tests/analyst/*` green
- [ ] `mypy --strict src/ig_qt/analyst/` clean
- [ ] `ruff check src/ tests/` clean
- [ ] Manual run (after `collect`): `uv run python -m ig_qt analyze` produces ≥1 row in `post_drafts`
- [ ] Run twice in a row: same news → second run picks different angle OR low confidence triggers evergreen
- [ ] Resolved OD-1 (9router): `Router9Provider` confirmed working OR config switched to `openai`/`anthropic`/`gemini`
- [ ] One-shot evergreen seeding: `uv run python scripts/generate_evergreen.py` populates ≥10 rows in `evergreen_drafts`

## M3 Self-Review Notes

- **Two-stage prompting cost:** Ranker is ~5K input + 500 output (cheap model). Composer is ~3K input + 2K output × 4 calls = bigger. Configure `cfg.llm.models.ranker = gemini-2.0-flash` (or similar cheap model) and `composer = claude-sonnet-4` (or similar quality model) to optimize.
- **Confidence threshold (0.6):** Tunable per-account. Start strict, loosen if too many evergreen fallbacks.
- **Story drafts share ranker output with feed:** ranker runs once per day, top-1 → feed, next 3 → stories. No separate ranker call.
- **Numbers come from DB only:** the prompt explicitly forbids inventing figures. If composer ignores, validation in M4 (composer module's caption finalizer) will detect placeholder-shaped tokens (`{...}`) that didn't substitute.
- **Evergreen LRU:** `pick_evergreen_draft` orders by `last_used_at NULLS FIRST` then `used_count` ascending. Older + less-used picked first.
- **Prompt versioning:** every draft stores `prompt_version` so prompt changes don't pollute history. When you ship `ranker.v2.md`, set `prompt_version="ranker.v2+composer.v1"`.
