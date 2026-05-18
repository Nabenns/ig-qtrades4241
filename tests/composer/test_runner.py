"""Tests for composer runner."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from ig_qt.composer.runner import ComposerRunner
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Post, PostDraft, PriceCache


@pytest.fixture
def seeded(tmp_path: Path) -> Any:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    with session_scope(engine) as s:
        s.add(
            PostDraft(
                post_type="feed",
                source_news_ids=[],
                topic_tag="fed_hawkish",
                angle="Fed hawkish",
                key_points=["a", "b"],
                caption_draft="Fed hawkish, USD/JPY watch level {usdjpy_close}",
                visual_spec={"type": "headline", "headline": "Fed Hawkish"},
                disclaimer_required=True,
                confidence=0.85,
                llm_provider="mock",
                llm_model="m",
                prompt_version="v1",
                status="pending",
            )
        )
        s.add(
            PriceCache(
                symbol="USD/JPY",
                timeframe="1d",
                fetched_at=datetime.now(UTC),
                ohlc_json=[
                    {
                        "t": "2026-05-17",
                        "open": 158,
                        "high": 159,
                        "low": 157,
                        "close": 158.42,
                    }
                ],
            )
        )
    return engine, tmp_path


@pytest.mark.asyncio
async def test_runner_promotes_draft_to_post(seeded: Any) -> None:
    engine, tmp_path = seeded
    Image.new("RGB", (256, 256), (10, 132, 255)).save(tmp_path / "logo.png")
    runner = ComposerRunner(
        engine=engine,
        data_dir=tmp_path,
        logo_path=tmp_path / "logo.png",
        handle="@x",
        scheduled_for_factory=lambda d: datetime.now(UTC) + timedelta(hours=1),
    )

    summary = await runner.run_once()
    assert summary.processed == 1
    assert summary.failed == 0

    with session_scope(engine) as s:
        posts = s.query(Post).all()
        assert len(posts) == 1
        post = posts[0]
        assert post.status == "ready"
        assert "158.42" in post.caption_final
        assert Path(post.asset_path).exists()
        drafts = s.query(PostDraft).all()
        assert drafts[0].status == "consumed"
