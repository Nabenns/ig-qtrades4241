"""Tests for evergreen pool."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from ig_qt.analyst.evergreen import pick_evergreen_draft, store_evergreen_drafts
from ig_qt.analyst.schemas import AngleDraft, VisualSpec
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import EvergreenDraft


def _draft(tag: str) -> AngleDraft:
    return AngleDraft(
        post_type="feed",
        topic_tag=tag,
        angle="Edukasi forex basics",
        key_points=["a", "b"],
        caption_draft="x" * 200,
        visual_spec=VisualSpec(type="headline", headline="hello"),
        disclaimer_required=True,
        confidence=0.7,
    )


def test_store_and_pick_evergreen(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    drafts = [_draft(f"topic_{i}") for i in range(3)]
    with session_scope(engine) as s:
        store_evergreen_drafts(s, drafts)
    with session_scope(engine) as s:
        rows = s.execute(select(EvergreenDraft)).scalars().all()
        assert len(rows) == 3

    with session_scope(engine) as s:
        first = pick_evergreen_draft(s)
        assert first is not None
        assert first.used_count == 1
        first_topic = first.topic_tag
    with session_scope(engine) as s:
        second = pick_evergreen_draft(s)
        assert second is not None
        assert second.topic_tag != first_topic
