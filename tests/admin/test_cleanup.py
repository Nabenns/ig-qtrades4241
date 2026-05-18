"""Tests for asset cleanup."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from ig_qt.admin.cleanup import cleanup_old_assets
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Post


def test_cleanup_removes_raw_for_old_published(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    posts_dir = tmp_path / "posts"
    old_dir = posts_dir / "1"
    old_dir.mkdir(parents=True)
    (old_dir / "raw.png").write_bytes(b"x")
    (old_dir / "feed.jpg").write_bytes(b"y")
    new_dir = posts_dir / "2"
    new_dir.mkdir(parents=True)
    (new_dir / "raw.png").write_bytes(b"x")

    old_time = datetime.now(UTC) - timedelta(days=45)
    new_time = datetime.now(UTC) - timedelta(days=2)
    with session_scope(engine) as s:
        s.add(
            Post(
                id=1,
                post_type="feed",
                caption_final="x",
                hashtags=[],
                asset_path=str(old_dir / "feed.jpg"),
                visual_type="headline",
                scheduled_for=old_time,
                published_at=old_time,
                status="published",
            )
        )
        s.add(
            Post(
                id=2,
                post_type="feed",
                caption_final="x",
                hashtags=[],
                asset_path=str(new_dir / "feed.jpg"),
                visual_type="headline",
                scheduled_for=new_time,
                published_at=new_time,
                status="published",
            )
        )

    summary = cleanup_old_assets(engine, posts_dir=posts_dir, age_days=30)
    assert summary.files_removed == 1
    assert not (old_dir / "raw.png").exists()
    assert (old_dir / "feed.jpg").exists()
    assert (new_dir / "raw.png").exists()
