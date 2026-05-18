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
                system=p.system,
                user=user,
                model=model,
                temperature=0.6,
                max_output_tokens=2500,
            )
            if resp.parsed is None:
                raise ValueError("angle generator returned non-JSON")
            draft = AngleDraft.model_validate(resp.parsed)
            if draft.post_type != post_type:
                raise ValueError(
                    f"post_type mismatch: expected {post_type}, got {draft.post_type}"
                )
            logger.info(
                "angle_ok post_type={} topic={} confidence={} tokens_in={} tokens_out={}",
                draft.post_type,
                draft.topic_tag,
                draft.confidence,
                resp.input_tokens,
                resp.output_tokens,
            )
            return draft
        except (ValidationError, ValueError) as exc:
            last_error = exc
            logger.warning("angle_retry attempt={} error={}", attempt, exc)
    raise RuntimeError(f"angle gen failed after {max_attempts} attempts: {last_error}")
