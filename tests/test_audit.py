"""Tests for content audit."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ig_qt.audit import audit_recent_posts
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Post, PostDraft


def _seed_published_post(
    engine: Any, *, caption: str, confidence: float = 0.85
) -> int:
    with session_scope(engine) as s:
        draft = PostDraft(
            post_type="feed",
            source_news_ids=[],
            topic_tag="t",
            angle="a",
            key_points=["a"],
            caption_draft=caption,
            visual_spec={"type": "headline", "headline": "x"},
            disclaimer_required=False,
            confidence=confidence,
            llm_provider="m",
            llm_model="m",
            prompt_version="v1",
            status="consumed",
        )
        s.add(draft)
        s.flush()
        post = Post(
            draft_id=draft.id,
            post_type="feed",
            caption_final=caption,
            hashtags=[],
            asset_path="x",
            visual_type="headline",
            scheduled_for=datetime.now(UTC),
            published_at=datetime.now(UTC),
            status="published",
            ig_media_id="x",
        )
        s.add(post)
        s.flush()
        return post.id


def test_audit_flags_banned_phrase(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    pid = _seed_published_post(engine, caption="Pasti naik. BUY EUR/USD sekarang!")
    flags = audit_recent_posts(engine, days=7)
    flagged_ids = {f.post_id for f in flags}
    assert pid in flagged_ids
    assert any("banned_phrase" in f.reason for f in flags if f.post_id == pid)


def test_audit_flags_low_confidence(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    pid = _seed_published_post(
        engine, caption="Update pasar normal saja", confidence=0.5
    )
    flags = audit_recent_posts(engine, days=7)
    assert pid in {f.post_id for f in flags}


def test_audit_passes_clean_post(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    pid = _seed_published_post(
        engine,
        caption="FOMC minutes hawkish. Watch USD/JPY level 158.",
        confidence=0.85,
    )
    flags = audit_recent_posts(engine, days=7)
    assert pid not in {f.post_id for f in flags}
