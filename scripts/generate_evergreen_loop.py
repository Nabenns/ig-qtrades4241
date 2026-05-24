"""LLM-based evergreen draft generator (looped, one draft per request).

Run: uv run python scripts/generate_evergreen_loop.py [--count N]

Better than the batch generator because Claude reliably produces a single
schema-valid draft per call. Defaults to 5 new drafts; idempotent against
existing topic_tags in the pool.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import ValidationError
from sqlalchemy import select

from ig_qt.analyst.evergreen import store_evergreen_drafts
from ig_qt.analyst.prompts.loader import load_prompt
from ig_qt.analyst.schemas import AngleDraft
from ig_qt.config import load_config
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.llm.factory import build_llm_provider
from ig_qt.llm.router_9 import Router9Provider
from ig_qt.logging_setup import configure_logging
from ig_qt.models import EvergreenDraft

# Topic seeds: the LLM rewrites these into full evergreen drafts. Each tuple is
# (topic, approach hint). Mix of risk, psychology, macro, chart, basics.
_TOPIC_SEEDS: list[tuple[str, str]] = [
    ("position sizing formula", "step-by-step calculation example with a $1000 account"),
    ("stop loss placement strategy", "structural vs ATR-based vs percentage methods"),
    ("trading session timing", "when each major session opens and which pairs to trade"),
    ("currency correlation", "which pairs move together and why it matters for risk"),
    ("breakout vs fakeout", "filters to distinguish real breakouts from traps"),
    ("FOMC meeting impact", "how to position before and after Fed announcements"),
    ("retail vs institutional flow", "what 'smart money' really means and how to spot it"),
    ("trailing stop techniques", "ATR trailing, swing trailing, and partial close strategies"),
    ("risk of ruin math", "calculating probability of blowing up account given win rate"),
    ("currency strength meter", "how to read multi-pair strength to find best trade direction"),
    ("news fade strategy", "trading the reversal after initial news spike"),
    ("range vs trending market", "identifying market regime before applying strategy"),
    ("higher timeframe bias", "why daily bias filters 70% of bad trades"),
    ("trading capital preservation", "drawdown recovery math and the 50% rule"),
    ("entry trigger confluence", "stacking 3+ confirmations before pulling the trigger"),
]


def _existing_tags(engine: Any) -> set[str]:
    with session_scope(engine) as s:
        return set(s.execute(select(EvergreenDraft.topic_tag)).scalars().all())


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    first_newline = text.find("\n")
    if first_newline == -1:
        return text
    inner = text[first_newline + 1 :]
    if inner.endswith("```"):
        inner = inner[:-3]
    return inner.strip()


async def _generate_one(
    *,
    provider: Any,
    composer_model: str,
    topic: str,
    approach: str,
    avoid_tags: set[str],
) -> AngleDraft | None:
    """Generate a single evergreen draft. Returns None on validation/network failure."""
    p = load_prompt("evergreen_single.v1")
    user = p.render_user(
        topic=topic,
        approach=approach,
        avoid_tags=", ".join(sorted(avoid_tags)) or "(none yet)",
    )
    try:
        resp = await provider.complete_json(
            system=p.system,
            user=user,
            model=composer_model,
            temperature=0.7,
            max_output_tokens=2000,
        )
    except Exception as exc:
        logger.warning("evergreen_single_llm_call_failed topic={} err={}", topic, exc)
        return None

    if resp.parsed is not None:
        raw = resp.parsed
    else:
        try:
            raw = json.loads(_strip_code_fence(resp.content))
        except json.JSONDecodeError:
            logger.warning(
                "evergreen_single_invalid_json topic={} preview={}",
                topic,
                resp.content[:300],
            )
            return None

    # Sometimes the model wraps the object in a list or under a key.
    if isinstance(raw, list) and raw:
        raw = raw[0]
    elif isinstance(raw, dict) and "draft" in raw and isinstance(raw["draft"], dict):
        raw = raw["draft"]

    try:
        return AngleDraft.model_validate(raw)
    except ValidationError as exc:
        logger.warning(
            "evergreen_single_validation_failed topic={} errors={} preview={}",
            topic,
            exc.error_count(),
            json.dumps(raw, ensure_ascii=False)[:300] if isinstance(raw, dict) else str(raw)[:300],
        )
        return None


async def _main(count: int) -> int:
    cfg = load_config(Path("config.yaml"))
    configure_logging(log_dir=cfg.paths.data_dir / "logs", level="INFO", json_logs=False)
    engine = build_engine(cfg.paths.data_dir / "ig_qt.db")
    init_schema(engine)

    # Use a long timeout — single draft is small but we don't want hiccups.
    if cfg.llm.provider == "router_9":
        provider: Any = Router9Provider(
            base_url=cfg.llm.base_url,
            api_key=cfg.llm.api_key.get_secret_value(),
            timeout=120.0,
        )
    else:
        provider = build_llm_provider(cfg.llm)

    avoid = _existing_tags(engine)
    logger.info("evergreen_loop_start avoid_count={} target_new={}", len(avoid), count)

    # Pick seeds deterministically (rotate by hash of existing-pool size for variety
    # across runs). Skip seeds whose slug looks like an existing tag.
    available_seeds = [
        (topic, approach)
        for topic, approach in _TOPIC_SEEDS
        if not any(_slug(topic) in tag for tag in avoid)
    ]
    if not available_seeds:
        logger.warning("evergreen_loop_no_unused_seeds — all topics covered")
        return 0

    target = min(count, len(available_seeds))
    new_drafts: list[AngleDraft] = []
    new_tags: set[str] = set()

    for topic, approach in available_seeds:
        if len(new_drafts) >= target:
            break
        draft = await _generate_one(
            provider=provider,
            composer_model=cfg.llm.composer_model,
            topic=topic,
            approach=approach,
            avoid_tags=avoid | new_tags,
        )
        if draft is None:
            continue
        if draft.topic_tag in avoid or draft.topic_tag in new_tags:
            logger.info("evergreen_loop_skip_duplicate_tag tag={}", draft.topic_tag)
            continue
        new_drafts.append(draft)
        new_tags.add(draft.topic_tag)
        logger.info("evergreen_loop_ok ({}/{}): {}", len(new_drafts), target, draft.topic_tag)

    if not new_drafts:
        logger.error("evergreen_loop_zero_success")
        return 1

    with session_scope(engine) as s:
        store_evergreen_drafts(s, new_drafts)
    logger.info("evergreen_loop_done inserted={}", len(new_drafts))
    return 0


def _slug(text: str) -> str:
    return "_".join(t for t in text.lower().split() if t.isalnum() or "_" in t)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate evergreen drafts via LLM, one at a time"
    )
    parser.add_argument("--count", type=int, default=5, help="Target new drafts (default: 5)")
    args = parser.parse_args()
    return asyncio.run(_main(count=args.count))


if __name__ == "__main__":
    sys.exit(main())
