"""Tests for stories_runtime."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Event, Post
from ig_qt.stories_runtime import generate_event_reminder_story


@pytest.fixture
def engine_path(tmp_path: Path) -> Any:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    Image.new("RGB", (256, 256), (10, 132, 255)).save(tmp_path / "logo.png")
    return engine, tmp_path


@pytest.mark.asyncio
async def test_generate_event_reminder_story_inserts_post(engine_path: Any) -> None:
    engine, tmp_path = engine_path
    now = datetime.now(UTC)
    with session_scope(engine) as s:
        s.add(
            Event(
                source="ff",
                event_time=now + timedelta(hours=2),
                country="US",
                currency="USD",
                name="CPI",
                impact="high",
                forecast="0.3%",
                previous="0.4%",
                actual=None,
                dedup_key="e1",
            )
        )

    post_id = await generate_event_reminder_story(
        engine=engine,
        data_dir=tmp_path,
        logo_path=tmp_path / "logo.png",
        handle="@x",
        scheduled_for=now,
    )
    assert post_id is not None

    with session_scope(engine) as s:
        post = s.query(Post).filter(Post.id == post_id).one()
        assert post.post_type == "story"
        assert post.status == "ready"
        assert Path(post.asset_path).exists()


@pytest.mark.asyncio
async def test_generate_event_reminder_returns_none_when_no_events(
    engine_path: Any,
) -> None:
    engine, tmp_path = engine_path
    now = datetime.now(UTC)
    post_id = await generate_event_reminder_story(
        engine=engine,
        data_dir=tmp_path,
        logo_path=tmp_path / "logo.png",
        handle="@x",
        scheduled_for=now,
    )
    assert post_id is None
