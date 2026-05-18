"""Storage cleanup for old post assets."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.db import session_scope
from ig_qt.models import Post


@dataclass(frozen=True, slots=True)
class CleanupSummary:
    files_removed: int
    bytes_freed: int


_KEEP_FILES: frozenset[str] = frozenset({"feed.jpg", "story.jpg"})


def cleanup_old_assets(
    engine: Engine, *, posts_dir: Path, age_days: int = 30
) -> CleanupSummary:
    cutoff = datetime.now(UTC) - timedelta(days=age_days)
    files_removed = 0
    bytes_freed = 0
    with session_scope(engine) as s:
        rows = list(
            s.execute(
                select(Post).where(
                    Post.status == "published",
                    Post.published_at <= cutoff,
                )
            ).scalars()
        )
        for p in rows:
            s.expunge(p)

    for post in rows:
        post_dir = posts_dir / str(post.id)
        if not post_dir.exists():
            continue
        for f in post_dir.iterdir():
            if not f.is_file():
                continue
            if f.name in _KEEP_FILES:
                continue
            try:
                size = f.stat().st_size
                f.unlink()
                files_removed += 1
                bytes_freed += size
            except OSError as exc:
                logger.warning("cleanup_skip path={} err={}", f, exc)
    logger.info(
        "cleanup_done files_removed={} bytes_freed={}", files_removed, bytes_freed
    )
    return CleanupSummary(files_removed=files_removed, bytes_freed=bytes_freed)
