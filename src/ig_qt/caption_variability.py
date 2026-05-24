"""Caption variability tracking.

Detects when the same opening phrase or stock prefix dominates recent posts.
Instagram's algorithm penalizes formulaic content; surfacing the pattern lets
us refresh openers/templates before reach drops.

Designed as a passive analyzer — no DB writes, just inspection + report.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.db import session_scope
from ig_qt.models import Post

# When the same opener appears more than this fraction of the window, we flag.
_DOMINANCE_THRESHOLD = 0.40
# Minimum posts before variability check is meaningful.
_MIN_SAMPLE = 5


@dataclass(frozen=True, slots=True)
class OpenerStats:
    """Frequency of a single caption-opening phrase."""

    opener: str
    count: int
    share: float


@dataclass(frozen=True, slots=True)
class VariabilityReport:
    window_days: int
    sample_size: int
    distinct_openers: int
    top_openers: list[OpenerStats]
    is_repetitive: bool


def _opening_line(caption: str) -> str:
    """First non-empty line of the caption, lowercased + stripped of punctuation tail."""
    for raw in caption.splitlines():
        line = raw.strip()
        if line:
            return line.rstrip(":.! ").lower()
    return ""


def analyze_variability(engine: Engine, *, days: int = 7) -> VariabilityReport:
    """Compute opener frequency over the last `days` days of created posts."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    with session_scope(engine) as s:
        rows = list(
            s.execute(
                select(Post.caption_final).where(Post.created_at >= cutoff)
            ).scalars()
        )

    counts: dict[str, int] = {}
    for cap in rows:
        if not cap:
            continue
        opener = _opening_line(cap)
        if not opener:
            continue
        counts[opener] = counts.get(opener, 0) + 1

    total = sum(counts.values())
    sorted_items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top = [
        OpenerStats(opener=k, count=v, share=v / total if total else 0.0)
        for k, v in sorted_items[:5]
    ]

    is_repetitive = (
        total >= _MIN_SAMPLE
        and bool(top)
        and top[0].share >= _DOMINANCE_THRESHOLD
    )

    return VariabilityReport(
        window_days=days,
        sample_size=total,
        distinct_openers=len(counts),
        top_openers=top,
        is_repetitive=is_repetitive,
    )


def format_variability_report(r: VariabilityReport) -> str:
    """Render variability report as Telegram Markdown."""
    if r.sample_size == 0:
        return f"📝 *Caption variability* (last {r.window_days}d): no posts yet."

    lines = [
        f"📝 *Caption variability* (last {r.window_days}d)",
        f"  posts: {r.sample_size} · distinct openers: {r.distinct_openers}",
    ]
    if r.is_repetitive:
        lines.append("  ⚠️ *Repetitive opener detected*:")
    else:
        lines.append("  Top openers:")
    for stat in r.top_openers:
        lines.append(
            f"    • {stat.share * 100:>4.0f}%  {stat.opener[:60]}  ({stat.count}x)"
        )
    if r.is_repetitive:
        lines.append("")
        lines.append(
            "  Tip: tambah varian opener di src/ig_qt/composer/caption.py"
            " atau diversifikasi prompt analyst."
        )
    return "\n".join(lines)


__all__: Sequence[str] = (
    "OpenerStats",
    "VariabilityReport",
    "analyze_variability",
    "format_variability_report",
)


def _log_summary(r: VariabilityReport) -> None:
    """For tests / observability."""
    logger.info(
        "variability sample={} distinct={} repetitive={}",
        r.sample_size,
        r.distinct_openers,
        r.is_repetitive,
    )
