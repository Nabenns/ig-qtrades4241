"""Evergreen content pool: pre-generated educational drafts for dry days."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

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
    row.last_used_at = datetime.now(UTC)
    session.flush()
    logger.info("evergreen_picked id={} topic={}", row.id, row.topic_tag)
    return row
