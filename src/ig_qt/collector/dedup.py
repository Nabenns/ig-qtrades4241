"""Insert helpers with INSERT OR IGNORE semantics via dedup_key."""
from __future__ import annotations

from collections.abc import Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from ig_qt.collector.base import NormalizedEvent, NormalizedNews
from ig_qt.models import Event, RawNews


def insert_news_dedup(session: Session, items: Sequence[NormalizedNews]) -> int:
    """Insert news items, skipping duplicates by dedup_key. Returns count inserted."""
    if not items:
        return 0
    keys = {it.dedup_key() for it in items}
    existing = set(
        session.execute(
            select(RawNews.dedup_key).where(RawNews.dedup_key.in_(keys))
        ).scalars()
    )
    inserted = 0
    seen_in_batch: set[str] = set()
    for it in items:
        k = it.dedup_key()
        if k in existing or k in seen_in_batch:
            continue
        seen_in_batch.add(k)
        session.add(
            RawNews(
                source=it.source,
                external_id=it.external_id,
                published_at=it.published_at,
                title=it.title,
                summary=it.summary,
                url=it.url,
                keywords=list(it.keywords),
                raw_payload=dict(it.raw_payload),
                dedup_key=k,
            )
        )
        inserted += 1
    logger.info("insert_news_dedup inserted={} skipped={}", inserted, len(items) - inserted)
    return inserted


def insert_events_dedup(session: Session, items: Sequence[NormalizedEvent]) -> int:
    if not items:
        return 0
    keys = {it.dedup_key() for it in items}
    existing = set(
        session.execute(select(Event.dedup_key).where(Event.dedup_key.in_(keys))).scalars()
    )
    inserted = 0
    seen_in_batch: set[str] = set()
    for it in items:
        k = it.dedup_key()
        if k in existing or k in seen_in_batch:
            continue
        seen_in_batch.add(k)
        session.add(
            Event(
                source=it.source,
                event_time=it.event_time,
                country=it.country,
                currency=it.currency,
                name=it.name,
                impact=it.impact,
                forecast=it.forecast,
                previous=it.previous,
                actual=it.actual,
                dedup_key=k,
            )
        )
        inserted += 1
    logger.info("insert_events_dedup inserted={} skipped={}", inserted, len(items) - inserted)
    return inserted
