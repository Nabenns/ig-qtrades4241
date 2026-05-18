"""Tests for rate limiter."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import IGAccountState, Post
from ig_qt.publisher.rate_limiter import (
    RateLimitDecision,
    check_rate_limit,
    is_paused,
    is_within_posting_window,
    offset_hours_for_timezone,
)


@pytest.fixture
def engine_path(tmp_path: Path) -> Any:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    return engine, tmp_path


def test_within_posting_window_06_to_23() -> None:
    base = datetime(2026, 5, 17, tzinfo=UTC)
    assert is_within_posting_window(
        base.replace(hour=8), start=6, end=23, tz_offset_hours=7
    )  # 15:00 WIB
    assert not is_within_posting_window(
        base.replace(hour=20), start=6, end=23, tz_offset_hours=7
    )  # 03:00 WIB next day


def test_pause_file_blocks(tmp_path: Path) -> None:
    pause = tmp_path / "PAUSE"
    assert not is_paused(pause)
    pause.write_text("")
    assert is_paused(pause)


def test_offset_hours_for_timezone() -> None:
    assert offset_hours_for_timezone("Asia/Jakarta") == 7
    assert offset_hours_for_timezone("UTC") == 0


def test_check_rate_limit_allows_when_under(engine_path: tuple[Any, Path]) -> None:
    engine, _ = engine_path
    with session_scope(engine) as s:
        s.add(IGAccountState(username="u"))
    decision = check_rate_limit(
        engine,
        post_type="feed",
        max_feed_per_day=2,
        max_feed_per_week=10,
        max_story_per_day=5,
    )
    assert decision == RateLimitDecision(allowed=True, reason=None)


def test_check_rate_limit_blocks_when_over(engine_path: tuple[Any, Path]) -> None:
    engine, _ = engine_path
    now = datetime.now(UTC)
    with session_scope(engine) as s:
        for _ in range(2):
            s.add(
                Post(
                    post_type="feed",
                    caption_final="x",
                    hashtags=[],
                    asset_path="x",
                    visual_type="headline",
                    scheduled_for=now,
                    status="published",
                    published_at=now,
                )
            )
    decision = check_rate_limit(
        engine,
        post_type="feed",
        max_feed_per_day=2,
        max_feed_per_week=10,
        max_story_per_day=5,
    )
    assert decision.allowed is False
    assert "feed daily limit" in (decision.reason or "")


def test_check_rate_limit_respects_pause_until(engine_path: tuple[Any, Path]) -> None:
    engine, _ = engine_path
    future = datetime.now(UTC) + timedelta(hours=1)
    with session_scope(engine) as s:
        s.add(IGAccountState(username="u", pause_until=future))
    decision = check_rate_limit(
        engine,
        post_type="feed",
        max_feed_per_day=2,
        max_feed_per_week=10,
        max_story_per_day=5,
    )
    assert decision.allowed is False
    assert "paused" in (decision.reason or "").lower()
