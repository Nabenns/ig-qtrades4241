"""Periodic content audit: flag published posts for human review."""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.db import session_scope
from ig_qt.models import Post, PostDraft

_BANNED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bpasti\s+(naik|turun)\b", re.IGNORECASE),
    re.compile(r"\bguaranteed?\s+(profit|gain|win)\b", re.IGNORECASE),
    re.compile(r"\b(BUY|SELL)\s+[A-Z]{3}/?[A-Z]{3}", re.IGNORECASE),
    re.compile(r"\bsignal\s+pasti\b", re.IGNORECASE),
    re.compile(r"\bdijamin\s+(naik|untung|profit)\b", re.IGNORECASE),
)

_LOW_CONFIDENCE = 0.7


@dataclass(frozen=True, slots=True)
class AuditFlag:
    post_id: int
    reason: str
    excerpt: str


def _check_banned_phrase(caption: str) -> str | None:
    for pat in _BANNED_PATTERNS:
        m = pat.search(caption)
        if m:
            return m.group(0)
    return None


def audit_recent_posts(engine: Engine, *, days: int = 7) -> list[AuditFlag]:
    """Audit posts published within the last `days` days. Returns flagged items."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    flags: list[AuditFlag] = []

    with session_scope(engine) as s:
        rows = list(
            s.execute(
                select(Post, PostDraft)
                .outerjoin(PostDraft, Post.draft_id == PostDraft.id)
                .where(Post.status == "published", Post.published_at >= cutoff)
            )
        )

    for post, draft in rows:
        cap = post.caption_final or ""
        banned = _check_banned_phrase(cap)
        if banned:
            flags.append(
                AuditFlag(
                    post_id=post.id,
                    reason=f"banned_phrase:{banned!r}",
                    excerpt=cap[:160],
                )
            )
            continue
        if draft is not None and draft.confidence < _LOW_CONFIDENCE:
            flags.append(
                AuditFlag(
                    post_id=post.id,
                    reason=f"low_confidence:{draft.confidence:.2f}",
                    excerpt=cap[:160],
                )
            )

    logger.info("audit_done flagged={} window_days={}", len(flags), days)
    return flags


def format_audit_report(flags: Sequence[AuditFlag]) -> str:
    if not flags:
        return "ig-qt audit: no flags this week."
    lines = [f"ig-qt audit: {len(flags)} flagged post(s):"]
    for f in flags[:20]:
        lines.append(f"  - #{f.post_id}: {f.reason}")
        lines.append(f"    > {f.excerpt}")
    if len(flags) > 20:
        lines.append(f"  ...and {len(flags) - 20} more.")
    return "\n".join(lines)
