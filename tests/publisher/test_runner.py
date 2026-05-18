"""Tests for publisher runner."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import IGAccountState, Post
from ig_qt.notifier import NoopNotifier
from ig_qt.publisher.ig_client import ChallengeRequiredError
from ig_qt.publisher.runner import PublisherRunner


class _FakeClient:
    def __init__(
        self,
        *,
        raise_on_feed: Exception | None = None,
        raise_on_story: Exception | None = None,
    ) -> None:
        self.feed_uploads: list[tuple[str, str]] = []
        self.story_uploads: list[str] = []
        self.warmup_calls = 0
        self.logged_in = True
        self._raise_feed = raise_on_feed
        self._raise_story = raise_on_story

    def ensure_logged_in(self) -> None:
        self.logged_in = True

    def warmup(self) -> None:
        self.warmup_calls += 1

    def publish_feed(self, *, asset: Path, caption: str) -> str:
        if self._raise_feed:
            raise self._raise_feed
        self.feed_uploads.append((str(asset), caption))
        return "media-feed"

    def publish_story(self, *, asset: Path) -> str:
        if self._raise_story:
            raise self._raise_story
        self.story_uploads.append(str(asset))
        return "media-story"


@pytest.fixture
def seeded(tmp_path: Path) -> Any:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    asset = tmp_path / "feed.jpg"
    Image.new("RGB", (1080, 1080), (10, 132, 255)).save(asset, "JPEG")
    now = datetime.now(UTC)
    with session_scope(engine) as s:
        s.add(IGAccountState(username="u"))
        s.add(
            Post(
                post_type="feed",
                caption_final="hello",
                hashtags=["#a"],
                asset_path=str(asset),
                visual_type="headline",
                scheduled_for=now - timedelta(minutes=1),
                status="ready",
            )
        )
    return engine, asset


@pytest.mark.asyncio
async def test_publisher_publishes_due_feed_post(
    seeded: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, _ = seeded
    fake = _FakeClient()

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    runner = PublisherRunner(
        engine=engine,
        client=fake,
        notifier=NoopNotifier(),
        pause_file=Path("/nonexistent/PAUSE"),
        max_feed_per_day=2,
        max_feed_per_week=10,
        max_story_per_day=5,
        posting_window_start_hour=0,
        posting_window_end_hour=24,
        tz_offset_hours=7,
        skip_day_seed="x",
        skip_day_probability=0.0,
        warmup_seed=1,
        sleep_range=(0.0, 0.0),
    )
    summary = await runner.run_due()
    assert summary.published == 1
    assert summary.failed == 0
    with session_scope(engine) as s:
        post = s.query(Post).first()
        assert post is not None
        assert post.status == "published"
        assert post.ig_media_id == "media-feed"


@pytest.mark.asyncio
async def test_publisher_pauses_on_challenge(
    seeded: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, _ = seeded
    fake = _FakeClient(raise_on_feed=ChallengeRequiredError("forced"))

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    runner = PublisherRunner(
        engine=engine,
        client=fake,
        notifier=NoopNotifier(),
        pause_file=Path("/nonexistent/PAUSE"),
        max_feed_per_day=2,
        max_feed_per_week=10,
        max_story_per_day=5,
        posting_window_start_hour=0,
        posting_window_end_hour=24,
        tz_offset_hours=7,
        skip_day_seed="x",
        skip_day_probability=0.0,
        warmup_seed=1,
        sleep_range=(0.0, 0.0),
    )
    summary = await runner.run_due()
    assert summary.failed == 1
    with session_scope(engine) as s:
        state = s.query(IGAccountState).first()
        assert state is not None
        assert state.pause_until is not None
        assert state.challenge_pending is True
        post = s.query(Post).first()
        assert post is not None
        assert post.status == "failed"


def test_publisher_blocked_by_pause_file(seeded: Any, tmp_path: Path) -> None:
    engine, _ = seeded
    pause_file = tmp_path / "PAUSE"
    pause_file.write_text("")
    fake = _FakeClient()
    runner = PublisherRunner(
        engine=engine,
        client=fake,
        notifier=NoopNotifier(),
        pause_file=pause_file,
        max_feed_per_day=2,
        max_feed_per_week=10,
        max_story_per_day=5,
        posting_window_start_hour=0,
        posting_window_end_hour=24,
        tz_offset_hours=7,
        skip_day_seed="x",
        skip_day_probability=0.0,
        warmup_seed=1,
        sleep_range=(0.0, 0.0),
    )
    summary = asyncio.run(runner.run_due())
    assert summary.published == 0
    assert summary.skipped_reason == "pause_file"
