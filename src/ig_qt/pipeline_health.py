"""Pipeline health checks + Telegram degradation alerts.

State-tracked alerts: each "alert key" has a row in `alert_state` so we can:
- Require N consecutive detections before notifying (avoid one-off blip noise)
- Apply a cooldown window so the same alert doesn't fire every cycle
- Reset counters when the condition clears

This makes the alert pipeline tolerable for runs every 15 minutes (96/day)
while still surfacing real degradation within ~30-45 minutes.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.analyst.runner import AnalystSummary
from ig_qt.collector.pipeline import CollectResult
from ig_qt.db import session_scope
from ig_qt.models import AlertState
from ig_qt.notifier import Notifier

# An alert needs to be detected this many cycles in a row before we send
# Telegram. Prevents spam on transient failures (e.g. one source flaking).
_DEFAULT_MIN_CONSECUTIVE = 3
# Once sent, we won't send the same alert again until this much time has passed.
# Real outages are noticed quickly; this keeps the channel readable.
_DEFAULT_COOLDOWN_HOURS = 6


@dataclass(frozen=True, slots=True)
class CollectAlert:
    """Reasons a collect run is considered degraded."""

    no_news: bool
    no_events: bool
    failed_sources: Sequence[str]

    @property
    def is_degraded(self) -> bool:
        return self.no_news or self.no_events or bool(self.failed_sources)


def evaluate_collect(result: CollectResult) -> CollectAlert:
    """Classify a collect run result. Pure function — no side effects."""
    return CollectAlert(
        no_news=result.news_inserted == 0,
        no_events=result.events_inserted == 0,
        failed_sources=tuple(result.failed_sources),
    )


def _should_send(
    *,
    engine: Engine,
    key: str,
    is_active: bool,
    min_consecutive: int,
    cooldown_hours: int,
) -> bool:
    """Update alert state for `key` and decide whether to send a notification.

    Side effects: writes to `alert_state` table.
    Returns True only when the condition has fired N consecutive times AND
    we're past the cooldown since the last send.
    """
    now = datetime.now(UTC)
    with session_scope(engine) as s:
        row = s.execute(
            select(AlertState).where(AlertState.key == key)
        ).scalar_one_or_none()

        if not is_active:
            # Condition cleared — reset counters but keep last_sent_at so
            # cooldown windows still apply if it flaps back on.
            if row is not None:
                row.consecutive_count = 0
                row.last_detected_at = None
                row.first_detected_at = None
            return False

        if row is None:
            row = AlertState(
                key=key,
                consecutive_count=1,
                first_detected_at=now,
                last_detected_at=now,
                last_sent_at=None,
            )
            s.add(row)
        else:
            row.consecutive_count += 1
            row.last_detected_at = now
            if row.first_detected_at is None:
                row.first_detected_at = now

        if row.consecutive_count < min_consecutive:
            return False

        if row.last_sent_at is not None:
            since_last = now - row.last_sent_at
            if since_last < timedelta(hours=cooldown_hours):
                return False

        # All checks passed — mark as sent.
        row.last_sent_at = now
        return True


async def alert_collect_if_degraded(
    *,
    notifier: Notifier,
    result: CollectResult,
    engine: Engine | None = None,
    min_consecutive: int = _DEFAULT_MIN_CONSECUTIVE,
    cooldown_hours: int = _DEFAULT_COOLDOWN_HOURS,
) -> None:
    """Send Telegram alert when a collect run looks unhealthy (with debouncing).

    `engine=None` falls back to immediate-send mode (used by tests + ad-hoc
    one-shot CLI invocations where we don't want to track state).
    """
    a = evaluate_collect(result)
    # Per-reason alert keys so different conditions don't mask each other.
    reasons: list[tuple[str, bool, str]] = [
        ("collect:no_news", a.no_news, "news_inserted=0"),
        (
            "collect:failed_sources",
            bool(a.failed_sources),
            f"failed_sources=[{', '.join(a.failed_sources)}]" if a.failed_sources else "",
        ),
    ]

    lines: list[str] = []
    for key, active, summary in reasons:
        if engine is None:
            # No state store — use simple immediate semantics.
            if active and summary:
                lines.append(f"⚠️ *Collector*: {summary}")
            continue
        send = _should_send(
            engine=engine,
            key=key,
            is_active=active,
            min_consecutive=min_consecutive,
            cooldown_hours=cooldown_hours,
        )
        if send and summary:
            lines.append(f"⚠️ *Collector*: {summary}")

    if not lines:
        return

    msg = "🚨 *Pipeline degraded*\n" + "\n".join(lines)
    try:
        await notifier.send(msg)
        logger.warning("collect_degradation_alert sent reasons={}", lines)
    except Exception as exc:
        logger.warning("collect_degradation_alert_send_failed err={}", exc)


async def alert_analyst_if_degraded(
    *,
    notifier: Notifier,
    summary: AnalystSummary,
    engine: Engine | None = None,
    min_consecutive: int = _DEFAULT_MIN_CONSECUTIVE,
    cooldown_hours: int = _DEFAULT_COOLDOWN_HOURS,
) -> None:
    """Send Telegram alert when analyst signals stale data or empty drafts."""
    news_stale = summary.stale_inputs and (
        summary.freshest_news_age_hours is None
        or summary.freshest_news_age_hours > 12
    )
    no_drafts = (
        summary.feed_drafts == 0
        and summary.story_drafts == 0
        and not summary.evergreen_used
    )
    using_evergreen = summary.evergreen_used

    reasons: list[tuple[str, bool, str]] = [
        (
            "analyst:news_stale",
            news_stale,
            (
                "news table empty"
                if summary.freshest_news_age_hours is None
                else f"freshest news is {summary.freshest_news_age_hours:.1f}h old"
            ),
        ),
        (
            "analyst:no_output",
            no_drafts,
            "no drafts produced AND no evergreen fallback",
        ),
        (
            "analyst:evergreen_fallback",
            using_evergreen,
            "using evergreen fallback (no fresh content)",
        ),
    ]

    lines: list[str] = []
    for key, active, text in reasons:
        if engine is None:
            if active and text:
                lines.append(f"⚠️ *Analyst*: {text}")
            continue
        send = _should_send(
            engine=engine,
            key=key,
            is_active=active,
            min_consecutive=min_consecutive,
            cooldown_hours=cooldown_hours,
        )
        if send and text:
            lines.append(f"⚠️ *Analyst*: {text}")

    if not lines:
        return

    msg = "🚨 *Pipeline degraded*\n" + "\n".join(lines)
    try:
        await notifier.send(msg)
        logger.warning("analyst_degradation_alert sent reasons={}", lines)
    except Exception as exc:
        logger.warning("analyst_degradation_alert_send_failed err={}", exc)
