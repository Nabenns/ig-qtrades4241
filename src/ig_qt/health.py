"""Mini FastAPI app exposing /health for monitoring."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from sqlalchemy import Engine, func, select

from ig_qt.db import session_scope
from ig_qt.models import IGAccountState, Post, PostDraft


def build_health_app(*, engine: Engine, pause_file: Path, version: str) -> FastAPI:
    app = FastAPI(
        title="ig-qt health", docs_url=None, redoc_url=None, openapi_url=None
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        with session_scope(engine) as s:
            state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
            pending_drafts = int(
                s.execute(
                    select(func.count())
                    .select_from(PostDraft)
                    .where(PostDraft.status == "pending")
                ).scalar()
                or 0
            )
            ready_posts = int(
                s.execute(
                    select(func.count())
                    .select_from(Post)
                    .where(Post.status == "ready")
                ).scalar()
                or 0
            )
            last_post = (
                state.last_post_at.isoformat() if state and state.last_post_at else None
            )
            pause_until = (
                state.pause_until.isoformat() if state and state.pause_until else None
            )
            challenge_pending = bool(state.challenge_pending) if state else False

        paused = pause_file.exists()
        if challenge_pending:
            status = "degraded"
        elif paused:
            status = "paused"
        else:
            status = "ok"

        return {
            "status": status,
            "version": version,
            "now": datetime.now(UTC).isoformat(),
            "last_post_at": last_post,
            "pause_until": pause_until,
            "challenge_pending": challenge_pending,
            "pending_drafts": pending_drafts,
            "ready_posts": ready_posts,
            "paused_via_file": paused,
        }

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "ig-qt", "version": version}

    return app
