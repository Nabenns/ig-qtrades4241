"""Generate scheduled story posts (event reminder, market recap) without LLM."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.composer.html_renderer import render_card
from ig_qt.composer.postprocess import finalize_story_image
from ig_qt.composer.stories import (
    build_event_reminder_context,
    build_market_recap_context,
)
from ig_qt.db import session_scope
from ig_qt.models import Event, Post, PriceCache


async def _render_and_persist(
    *,
    engine: Engine,
    template: str,
    context: dict[str, Any],
    caption: str,
    visual_type: str,
    data_dir: Path,
    logo_path: Path,
    handle: str,
    scheduled_for: datetime,
) -> int | None:
    with session_scope(engine) as s:
        placeholder = Post(
            post_type="story",
            caption_final=caption,
            hashtags=[],
            asset_path="pending",
            visual_type=visual_type,
            scheduled_for=scheduled_for,
            status="ready",
        )
        s.add(placeholder)
        s.flush()
        post_id = placeholder.id

    out_dir = data_dir / "posts" / str(post_id)
    raw = out_dir / "raw.png"
    final = out_dir / "story.jpg"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        await render_card(
            template=template,
            context={**context, "handle": handle, "orientation": "story"},
            out_path=raw,
            viewport=(1080, 1920),
        )
        finalize_story_image(src=raw, dst=final, logo_path=logo_path, handle=handle)
    except Exception as exc:
        logger.error("story_render_failed template={} err={}", template, exc)
        with session_scope(engine) as s:
            p = s.execute(select(Post).where(Post.id == post_id)).scalar_one()
            p.status = "failed"
            p.error_log = str(exc)
        return None

    with session_scope(engine) as s:
        p = s.execute(select(Post).where(Post.id == post_id)).scalar_one()
        p.asset_path = str(final)
    return post_id


async def generate_event_reminder_story(
    *,
    engine: Engine,
    data_dir: Path,
    logo_path: Path,
    handle: str,
    scheduled_for: datetime,
    window_hours: int = 12,
) -> int | None:
    now = datetime.now(UTC)
    with session_scope(engine) as s:
        events = list(s.execute(select(Event).order_by(Event.event_time)).scalars())
        for e in events:
            s.expunge(e)
    ctx = build_event_reminder_context(events=events, now=now, window_hours=window_hours)
    if not ctx["events"]:
        logger.info("event_reminder_no_events")
        return None
    caption = (
        "Event macro penting hari ini. Watch volatilitas di sekitar window time. "
        "Mana yang paling kamu pantau?"
    )
    return await _render_and_persist(
        engine=engine,
        template="event_card.html",
        context=ctx,
        caption=caption,
        visual_type="event",
        data_dir=data_dir,
        logo_path=logo_path,
        handle=handle,
        scheduled_for=scheduled_for,
    )


async def generate_market_recap_story(
    *,
    engine: Engine,
    data_dir: Path,
    logo_path: Path,
    handle: str,
    scheduled_for: datetime,
    symbols: list[str],
) -> int | None:
    with session_scope(engine) as s:
        rows = list(s.execute(select(PriceCache)).scalars())
    latest_per_symbol: dict[str, list[dict[str, Any]]] = {}
    latest_fetched: dict[str, datetime] = {}
    for r in rows:
        if r.symbol not in symbols:
            continue
        prev = latest_fetched.get(r.symbol)
        if prev is None or r.fetched_at > prev:
            latest_per_symbol[r.symbol] = list(r.ohlc_json)
            latest_fetched[r.symbol] = r.fetched_at
    ctx = build_market_recap_context(latest_prices=latest_per_symbol, symbols=symbols)
    if not ctx["recaps"]:
        logger.info("market_recap_no_data")
        return None
    caption = (
        "Recap harian pair major. Closing vs previous close. "
        "Pair mana yang paling kamu watch besok?"
    )
    return await _render_and_persist(
        engine=engine,
        template="market_recap.html",
        context=ctx,
        caption=caption,
        visual_type="recap",
        data_dir=data_dir,
        logo_path=logo_path,
        handle=handle,
        scheduled_for=scheduled_for,
    )
