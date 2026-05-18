"""Pre-publish rate limit checks."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, func, select

from ig_qt.db import session_scope
from ig_qt.models import IGAccountState, Post


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    reason: str | None


def is_paused(pause_file: Path) -> bool:
    return pause_file.exists()


def is_within_posting_window(
    now_utc: datetime, *, start: int, end: int, tz_offset_hours: int
) -> bool:
    local = now_utc.astimezone(timezone(timedelta(hours=tz_offset_hours)))
    return start <= local.hour < end


def offset_hours_for_timezone(tz_name: str, *, ref: datetime | None = None) -> int:
    """Return UTC offset in hours for a given IANA tz at `ref` (default: now)."""
    tz = ZoneInfo(tz_name)
    ref = ref or datetime.now(UTC)
    delta = ref.astimezone(tz).utcoffset() or timedelta(0)
    return int(delta.total_seconds() // 3600)


def _count_published_since(engine: Engine, *, post_type: str, since: datetime) -> int:
    with session_scope(engine) as s:
        n = (
            s.execute(
                select(func.count())
                .select_from(Post)
                .where(
                    Post.post_type == post_type,
                    Post.status == "published",
                    Post.published_at >= since,
                )
            ).scalar()
            or 0
        )
        return int(n)


def check_rate_limit(
    engine: Engine,
    *,
    post_type: str,
    max_feed_per_day: int,
    max_feed_per_week: int,
    max_story_per_day: int,
) -> RateLimitDecision:
    now = datetime.now(UTC)
    with session_scope(engine) as s:
        state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
    if state and state.pause_until is not None:
        pause_until = state.pause_until
        if pause_until.tzinfo is None:
            pause_until = pause_until.replace(tzinfo=UTC)
        if pause_until > now:
            return RateLimitDecision(False, f"account paused until {pause_until.isoformat()}")
    if state and state.challenge_pending:
        return RateLimitDecision(False, "challenge pending — manual resolve required")

    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    if post_type == "feed":
        daily = _count_published_since(engine, post_type="feed", since=day_ago)
        if daily >= max_feed_per_day:
            return RateLimitDecision(
                False, f"feed daily limit reached ({daily}/{max_feed_per_day})"
            )
        weekly = _count_published_since(engine, post_type="feed", since=week_ago)
        if weekly >= max_feed_per_week:
            return RateLimitDecision(
                False, f"feed weekly limit reached ({weekly}/{max_feed_per_week})"
            )
    elif post_type == "story":
        daily = _count_published_since(engine, post_type="story", since=day_ago)
        if daily >= max_story_per_day:
            return RateLimitDecision(
                False, f"story daily limit reached ({daily}/{max_story_per_day})"
            )
    return RateLimitDecision(True, None)
