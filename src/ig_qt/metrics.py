"""Weekly pipeline metrics report.

Aggregates last-N-days activity from PostDraft, Post, ReviewMessage tables
into a human-readable Telegram message. Designed to run as a scheduled job
(cron-like) or one-shot via admin command.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import Engine, func, select

from ig_qt.db import session_scope
from ig_qt.models import EvergreenDraft, Post, PostDraft, RawNews, ReviewMessage


@dataclass(frozen=True, slots=True)
class WeeklyMetrics:
    """Snapshot of pipeline activity over a window."""

    window_days: int
    drafts_total: int
    drafts_feed: int
    drafts_story: int
    drafts_avg_confidence: float | None
    drafts_evergreen_used: int
    posts_total: int
    posts_approved: int
    posts_rejected: int
    posts_review_pending: int
    news_inserted: int
    evergreen_pool_size: int

    @property
    def approval_rate(self) -> float | None:
        """Approved / (approved + rejected). None when nothing was decided."""
        decided = self.posts_approved + self.posts_rejected
        return None if decided == 0 else self.posts_approved / decided


def collect_weekly_metrics(engine: Engine, *, days: int = 7) -> WeeklyMetrics:
    """Compute metrics over the last `days` days."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    with session_scope(engine) as s:
        # PostDrafts created in window
        drafts_total = (
            s.execute(
                select(func.count())
                .select_from(PostDraft)
                .where(PostDraft.created_at >= cutoff)
            ).scalar()
            or 0
        )
        drafts_feed = (
            s.execute(
                select(func.count())
                .select_from(PostDraft)
                .where(PostDraft.created_at >= cutoff, PostDraft.post_type == "feed")
            ).scalar()
            or 0
        )
        drafts_story = (
            s.execute(
                select(func.count())
                .select_from(PostDraft)
                .where(PostDraft.created_at >= cutoff, PostDraft.post_type == "story")
            ).scalar()
            or 0
        )
        drafts_avg_conf = s.execute(
            select(func.avg(PostDraft.confidence)).where(PostDraft.created_at >= cutoff)
        ).scalar()
        drafts_evergreen = (
            s.execute(
                select(func.count())
                .select_from(PostDraft)
                .where(
                    PostDraft.created_at >= cutoff,
                    PostDraft.llm_provider == "evergreen",
                )
            ).scalar()
            or 0
        )

        # Posts created in window — broken down by status
        posts_total = (
            s.execute(
                select(func.count())
                .select_from(Post)
                .where(Post.created_at >= cutoff)
            ).scalar()
            or 0
        )
        posts_approved = (
            s.execute(
                select(func.count())
                .select_from(Post)
                .where(Post.created_at >= cutoff, Post.status.in_(["approved", "published"]))
            ).scalar()
            or 0
        )
        posts_rejected = (
            s.execute(
                select(func.count())
                .select_from(Post)
                .where(Post.created_at >= cutoff, Post.status == "rejected")
            ).scalar()
            or 0
        )
        posts_review = (
            s.execute(
                select(func.count())
                .select_from(Post)
                .where(Post.created_at >= cutoff, Post.status == "review")
            ).scalar()
            or 0
        )

        # News health
        news_inserted = (
            s.execute(
                select(func.count())
                .select_from(RawNews)
                .where(RawNews.created_at >= cutoff)
            ).scalar()
            or 0
        )
        evergreen_pool = (
            s.execute(select(func.count()).select_from(EvergreenDraft)).scalar() or 0
        )

    return WeeklyMetrics(
        window_days=days,
        drafts_total=drafts_total,
        drafts_feed=drafts_feed,
        drafts_story=drafts_story,
        drafts_avg_confidence=float(drafts_avg_conf) if drafts_avg_conf is not None else None,
        drafts_evergreen_used=drafts_evergreen,
        posts_total=posts_total,
        posts_approved=posts_approved,
        posts_rejected=posts_rejected,
        posts_review_pending=posts_review,
        news_inserted=news_inserted,
        evergreen_pool_size=evergreen_pool,
    )


def format_weekly_report(m: WeeklyMetrics) -> str:
    """Render metrics as a Telegram-friendly Markdown message."""
    conf_txt = f"{m.drafts_avg_confidence:.2f}" if m.drafts_avg_confidence is not None else "n/a"
    rate = m.approval_rate
    rate_txt = f"{rate * 100:.0f}%" if rate is not None else "n/a"

    lines = [
        f"📊 *ig-qt weekly* (last {m.window_days}d)",
        "",
        "*Drafts*",
        f"  total: {m.drafts_total} (feed {m.drafts_feed} · story {m.drafts_story})",
        f"  avg confidence: {conf_txt}",
        f"  evergreen fallback: {m.drafts_evergreen_used}",
        "",
        "*Posts*",
        f"  total: {m.posts_total}",
        f"  approved: {m.posts_approved}",
        f"  rejected: {m.posts_rejected}",
        f"  pending review: {m.posts_review_pending}",
        f"  approval rate: {rate_txt}",
        "",
        "*Health*",
        f"  news ingested: {m.news_inserted}",
        f"  evergreen pool: {m.evergreen_pool_size}",
    ]
    return "\n".join(lines)


def render_metrics_text(engine: Engine, *, days: int = 7) -> str:
    """Convenience: collect + format in one call."""
    m = collect_weekly_metrics(engine, days=days)
    text = format_weekly_report(m)
    logger.info(
        "weekly_metrics_rendered drafts={} posts={} approval_rate={}",
        m.drafts_total,
        m.posts_total,
        m.approval_rate,
    )
    return text


# Keep a tiny export for tests / CLI introspection
__all__: Sequence[str] = (
    "WeeklyMetrics",
    "collect_weekly_metrics",
    "format_weekly_report",
    "render_metrics_text",
)


# Suppress unused-import warning for ReviewMessage (kept for future expansion)
_ = ReviewMessage
