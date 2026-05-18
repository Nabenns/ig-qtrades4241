"""Tests for warmup mode admin helpers."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ig_qt.admin.warmup_mode import (
    WarmupStatus,
    assess_readiness,
    disable_warmup,
    enable_warmup,
)
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import IGAccountState


def test_enable_then_disable(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    with session_scope(engine) as s:
        s.add(IGAccountState(username="u"))

    enable_warmup(engine)
    with session_scope(engine) as s:
        state = s.query(IGAccountState).first()
        assert state is not None
        assert state.warmup_active is True
        assert state.warmup_started_at is not None

    disable_warmup(engine)
    with session_scope(engine) as s:
        state = s.query(IGAccountState).first()
        assert state is not None
        assert state.warmup_active is False


def test_assess_readiness_returns_warmup_active() -> None:
    state = IGAccountState(
        username="u",
        warmup_active=True,
        warmup_started_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    status = assess_readiness(state, now=datetime(2026, 5, 15, tzinfo=UTC))
    assert isinstance(status, WarmupStatus)
    assert status.warmup_active is True
    assert status.days_in_warmup >= 14
