"""Tests for /health endpoint."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.health import build_health_app
from ig_qt.models import IGAccountState, Post, PostDraft


def _seed(engine: Any, *, paused: bool = False) -> None:
    with session_scope(engine) as s:
        s.add(
            IGAccountState(
                username="u",
                last_post_at=datetime.now(UTC) - timedelta(hours=2),
                pause_until=(
                    datetime.now(UTC) + timedelta(hours=1) if paused else None
                ),
                challenge_pending=paused,
            )
        )
        s.add(
            PostDraft(
                post_type="feed",
                source_news_ids=[],
                topic_tag="t",
                angle="a",
                key_points=["a"],
                caption_draft="x" * 200,
                visual_spec={"type": "headline", "headline": "x"},
                disclaimer_required=False,
                confidence=0.8,
                llm_provider="m",
                llm_model="m",
                prompt_version="v1",
                status="pending",
            )
        )
        s.add(
            Post(
                post_type="feed",
                caption_final="x",
                hashtags=[],
                asset_path="x",
                visual_type="headline",
                scheduled_for=datetime.now(UTC),
                status="ready",
            )
        )


def test_health_returns_ok_when_not_paused(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    _seed(engine, paused=False)
    pause_file = tmp_path / "PAUSE"
    app = build_health_app(engine=engine, pause_file=pause_file, version="0.1.0")
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["pending_drafts"] == 1
    assert body["ready_posts"] == 1
    assert body["challenge_pending"] is False


def test_health_returns_paused_when_pause_file_exists(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    _seed(engine)
    pause_file = tmp_path / "PAUSE"
    pause_file.write_text("")
    app = build_health_app(engine=engine, pause_file=pause_file, version="0.1.0")
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.json()["status"] == "paused"


def test_health_returns_challenge_when_state_pending(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    _seed(engine, paused=True)
    app = build_health_app(engine=engine, pause_file=tmp_path / "PAUSE", version="0.1.0")
    client = TestClient(app)
    body = client.get("/health").json()
    assert body["challenge_pending"] is True
    assert body["status"] == "degraded"
