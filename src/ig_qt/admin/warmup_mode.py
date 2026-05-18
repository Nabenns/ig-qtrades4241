"""Warmup mode admin helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.db import session_scope
from ig_qt.models import IGAccountState


@dataclass(frozen=True, slots=True)
class WarmupStatus:
    warmup_active: bool
    warmup_started_at: datetime | None
    days_in_warmup: int
    last_post_at: datetime | None


def enable_warmup(engine: Engine) -> None:
    with session_scope(engine) as s:
        state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
        if state is None:
            state = IGAccountState(username="unknown")
            s.add(state)
            s.flush()
        state.warmup_active = True
        state.warmup_started_at = datetime.now(UTC)
    logger.info("warmup_enabled")


def disable_warmup(engine: Engine) -> None:
    with session_scope(engine) as s:
        state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
        if state is None:
            return
        state.warmup_active = False
    logger.info("warmup_disabled")


def assess_readiness(state: IGAccountState, *, now: datetime) -> WarmupStatus:
    started = state.warmup_started_at
    if started is not None:
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        days = max(0, (now - started).days)
    else:
        days = 0
    return WarmupStatus(
        warmup_active=bool(state.warmup_active),
        warmup_started_at=state.warmup_started_at,
        days_in_warmup=days,
        last_post_at=state.last_post_at,
    )
