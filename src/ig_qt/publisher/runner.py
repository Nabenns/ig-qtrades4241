"""Publish due posts with anti-ban tactics + structured logging."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.db import session_scope
from ig_qt.models import IGAccountState, Post, PublishLog
from ig_qt.notifier import Notifier
from ig_qt.publisher.ig_client import (
    ChallengeRequiredError,
    FeedbackBlockedError,
    IGClientError,
    LoginExpiredError,
)
from ig_qt.publisher.rate_limiter import (
    check_rate_limit,
    is_paused,
    is_within_posting_window,
)
from ig_qt.publisher.skip_day import should_skip_day
from ig_qt.publisher.warmup import simulate_pre_publish_activity


class _PubClient(Protocol):
    def ensure_logged_in(self) -> None: ...
    def warmup(self) -> None: ...
    def publish_feed(self, *, asset: Path, caption: str) -> str: ...
    def publish_story(self, *, asset: Path) -> str: ...


@dataclass(frozen=True, slots=True)
class PublishResult:
    published: int
    failed: int
    skipped_reason: str | None = None


class PublisherRunner:
    def __init__(
        self,
        *,
        engine: Engine,
        client: _PubClient,
        notifier: Notifier,
        pause_file: Path,
        max_feed_per_day: int,
        max_feed_per_week: int,
        max_story_per_day: int,
        posting_window_start_hour: int,
        posting_window_end_hour: int,
        tz_offset_hours: int,
        skip_day_seed: str,
        skip_day_probability: float,
        warmup_seed: int,
        sleep_range: tuple[float, float] = (8.0, 15.0),
    ) -> None:
        self._engine = engine
        self._client = client
        self._notifier = notifier
        self._pause_file = pause_file
        self._max_feed_per_day = max_feed_per_day
        self._max_feed_per_week = max_feed_per_week
        self._max_story_per_day = max_story_per_day
        self._win_start = posting_window_start_hour
        self._win_end = posting_window_end_hour
        self._tz_offset = tz_offset_hours
        self._skip_seed = skip_day_seed
        self._skip_prob = skip_day_probability
        self._warmup_seed = warmup_seed
        self._sleep_range = sleep_range

    async def run_due(self) -> PublishResult:
        now = datetime.now(UTC)
        if is_paused(self._pause_file):
            logger.info("publisher_skipped reason=pause_file")
            return PublishResult(0, 0, "pause_file")
        if not is_within_posting_window(
            now,
            start=self._win_start,
            end=self._win_end,
            tz_offset_hours=self._tz_offset,
        ):
            logger.info("publisher_skipped reason=outside_window")
            return PublishResult(0, 0, "outside_window")

        with session_scope(self._engine) as s:
            warmup_state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
            if warmup_state is not None and warmup_state.warmup_active:
                logger.info("publisher_skipped reason=warmup_active")
                return PublishResult(0, 0, "warmup_active")

        with session_scope(self._engine) as s:
            posts = list(
                s.execute(
                    select(Post)
                    .where(Post.status == "ready", Post.scheduled_for <= now)
                    .order_by(Post.scheduled_for)
                ).scalars()
            )
            for p in posts:
                s.expunge(p)

        if not posts:
            return PublishResult(0, 0, "no_due_posts")

        skip_today = should_skip_day(
            now.date(), probability=self._skip_prob, seed=self._skip_seed
        )

        published = 0
        failed = 0

        try:
            self._client.ensure_logged_in()
        except IGClientError as exc:
            logger.error("publisher_login_failed err={}", exc)
            await self._notifier.send(f"⚠️ ig-qt: login gagal — {exc}")
            return PublishResult(0, len(posts), "login_failed")

        for post in posts:
            if skip_today and post.post_type == "feed":
                logger.info("publisher_skip_day_feed id={}", post.id)
                continue

            decision = check_rate_limit(
                self._engine,
                post_type=post.post_type,
                max_feed_per_day=self._max_feed_per_day,
                max_feed_per_week=self._max_feed_per_week,
                max_story_per_day=self._max_story_per_day,
            )
            if not decision.allowed:
                logger.warning("publisher_rate_limited reason={}", decision.reason)
                continue

            try:
                await simulate_pre_publish_activity(
                    self._client,
                    sleep_min=self._sleep_range[0],
                    sleep_max=self._sleep_range[1],
                    seed=self._warmup_seed + post.id,
                )
                t0 = time.monotonic()
                if post.post_type == "feed":
                    pk = self._client.publish_feed(
                        asset=Path(post.asset_path), caption=post.caption_final
                    )
                else:
                    pk = self._client.publish_story(asset=Path(post.asset_path))
                took_ms = int((time.monotonic() - t0) * 1000)
                self._mark_published(post.id, pk, took_ms)
                await self._notifier.send(
                    f"✅ ig-qt: published {post.post_type} (post_id={post.id}, ig_pk={pk})"
                )
                published += 1
            except ChallengeRequiredError as exc:
                self._mark_failed(post.id, "challenge", str(exc))
                self._set_pause(timedelta(days=7), challenge=True)
                await self._notifier.send(
                    f"🚨 ig-qt: ChallengeRequired — manual resolve! ({exc})"
                )
                failed += 1
                break
            except FeedbackBlockedError as exc:
                self._mark_failed(post.id, "feedback_blocked", str(exc))
                self._set_pause(timedelta(hours=24))
                await self._notifier.send(
                    f"⚠️ ig-qt: action blocked, pausing 24h ({exc})"
                )
                failed += 1
                break
            except LoginExpiredError as exc:
                self._mark_failed(post.id, "login_expired", str(exc))
                await self._notifier.send(
                    "⚠️ ig-qt: session expired — re-login required"
                )
                failed += 1
                break
            except IGClientError as exc:
                self._mark_failed(post.id, "ig_error", str(exc))
                failed += 1
            except Exception as exc:
                self._mark_failed(post.id, "unexpected", str(exc))
                logger.exception("publisher_unexpected_error post_id={}", post.id)
                failed += 1

        logger.info("publisher_run_done published={} failed={}", published, failed)
        return PublishResult(published=published, failed=failed)

    def _mark_published(self, post_id: int, pk: str, took_ms: int) -> None:
        now = datetime.now(UTC)
        with session_scope(self._engine) as s:
            post = s.execute(select(Post).where(Post.id == post_id)).scalar_one()
            post.status = "published"
            post.ig_media_id = pk
            post.published_at = now
            s.add(
                PublishLog(
                    post_id=post_id,
                    ig_media_id=pk,
                    attempt_no=1,
                    status="success",
                    took_ms=took_ms,
                )
            )
            state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
            if state:
                state.last_post_at = now
                state.daily_post_count += 1

    def _mark_failed(self, post_id: int, error_type: str, error_message: str) -> None:
        with session_scope(self._engine) as s:
            post = s.execute(select(Post).where(Post.id == post_id)).scalar_one()
            post.status = "failed"
            post.error_log = error_message[:2000]
            s.add(
                PublishLog(
                    post_id=post_id,
                    attempt_no=1,
                    status="failed",
                    error_type=error_type,
                    error_message=error_message[:2000],
                )
            )

    def _set_pause(self, duration: timedelta, *, challenge: bool = False) -> None:
        with session_scope(self._engine) as s:
            state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
            if state is None:
                return
            state.pause_until = datetime.now(UTC) + duration
            if challenge:
                state.challenge_pending = True
