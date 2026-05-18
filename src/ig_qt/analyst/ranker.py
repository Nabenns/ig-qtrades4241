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
                system=p.system,
                user=user,
                model=model,
                temperature=0.2,
                max_output_tokens=1500,
            )
            if resp.parsed is None:
                raise ValueError("ranker returned non-JSON content")
            output = RankerOutput.model_validate(resp.parsed)
            logger.info(
                "ranker_ok attempt={} count={} input_tokens={} output_tokens={}",
                attempt,
                len(output.ranked),
                resp.input_tokens,
                resp.output_tokens,
            )
            return output
        except (ValidationError, ValueError) as exc:
            last_error = exc
            logger.warning("ranker_retry attempt={} error={}", attempt, exc)
    raise RuntimeError(f"ranker failed after {max_attempts} attempts: {last_error}")
