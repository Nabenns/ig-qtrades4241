# M5 Publisher + Scheduler — Implementation Plan

> **Parent:** [`../2026-05-17-ig-forex-automation.md`](../2026-05-17-ig-forex-automation.md)
> **Prereq:** M1–M4 complete.

**Goal:** Publish ready posts to Instagram via instagrapi with layered anti-ban tactics (session persistence, jitter, pre-warmup, rate limits, kill switch, pause-on-challenge). Wire APScheduler with persistent jobstore to run the full pipeline (collect → analyze → compose → publish + story builders) on cron triggers with random jitter. End state: long-running `python -m ig_qt run` orchestrates everything; `data/PAUSE` file pauses publisher mid-run.

**Files created in M5:**
- `src/ig_qt/publisher/__init__.py`, `ig_client.py`, `warmup.py`, `rate_limiter.py`, `feed.py`, `story.py`, `runner.py`
- `src/ig_qt/scheduler.py`
- `src/ig_qt/stories_runtime.py` (event reminder + recap story job that builds + composes + publishes in one go)
- `tests/publisher/test_*.py`
- `tests/test_scheduler.py`
- `scripts/ig_login_first_time.py`
- Modify: `pyproject.toml` (add deps), `src/ig_qt/app.py`, `src/ig_qt/__main__.py`

**New dependencies:** `instagrapi>=2.1`, `apscheduler>=3.10`.

---

## Task 5.1: Add dependencies + publisher scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ig_qt/publisher/__init__.py`
- Create: `tests/publisher/__init__.py`

- [ ] **Step 1: Add deps**

```toml
    "instagrapi>=2.1",
    "apscheduler>=3.10",
```

- [ ] **Step 2: Sync**

```bash
uv sync
```

- [ ] **Step 3: Create empty package**

`src/ig_qt/publisher/__init__.py`:

```python
"""Instagram publishing via instagrapi with anti-ban tactics."""
from __future__ import annotations
```

`tests/publisher/__init__.py`: empty.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/ig_qt/publisher/__init__.py tests/publisher/__init__.py
git commit -m "chore(publisher): add deps and package scaffold"
```

---

## Task 5.2: Rate limiter

**Files:**
- Create: `src/ig_qt/publisher/rate_limiter.py`
- Create: `tests/publisher/test_rate_limiter.py`

- [ ] **Step 1: Write failing test**

`tests/publisher/test_rate_limiter.py`:

```python
"""Tests for rate limiter."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import IGAccountState, Post, PublishLog
from ig_qt.publisher.rate_limiter import (
    RateLimitDecision,
    check_rate_limit,
    is_within_posting_window,
    is_paused,
)


@pytest.fixture
def engine_path(tmp_path: Path):  # type: ignore[no-untyped-def]
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    return engine, tmp_path


def test_within_posting_window_06_to_23() -> None:
    base = datetime(2026, 5, 17, tzinfo=timezone.utc)
    assert is_within_posting_window(
        base.replace(hour=8), start=6, end=23, tz_offset_hours=7
    )  # 15:00 WIB
    assert not is_within_posting_window(
        base.replace(hour=20), start=6, end=23, tz_offset_hours=7
    )  # 03:00 WIB


def test_pause_file_blocks(tmp_path: Path) -> None:
    pause = tmp_path / "PAUSE"
    assert not is_paused(pause)
    pause.write_text("")
    assert is_paused(pause)


def test_check_rate_limit_allows_when_under(engine_path: tuple) -> None:
    engine, _ = engine_path
    with session_scope(engine) as s:
        s.add(IGAccountState(username="u"))
    decision = check_rate_limit(
        engine,
        post_type="feed",
        max_feed_per_day=2,
        max_feed_per_week=10,
        max_story_per_day=5,
    )
    assert decision == RateLimitDecision(allowed=True, reason=None)


def test_check_rate_limit_blocks_when_over(engine_path: tuple) -> None:
    engine, _ = engine_path
    now = datetime.now(timezone.utc)
    with session_scope(engine) as s:
        for _ in range(2):
            s.add(
                Post(
                    post_type="feed",
                    caption_final="x",
                    hashtags=[],
                    asset_path="x",
                    visual_type="headline",
                    scheduled_for=now,
                    status="published",
                    published_at=now,
                )
            )
    decision = check_rate_limit(
        engine,
        post_type="feed",
        max_feed_per_day=2,
        max_feed_per_week=10,
        max_story_per_day=5,
    )
    assert decision.allowed is False
    assert "feed daily limit" in (decision.reason or "")


def test_check_rate_limit_respects_pause_until(engine_path: tuple) -> None:
    engine, _ = engine_path
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    with session_scope(engine) as s:
        s.add(IGAccountState(username="u", pause_until=future))
    decision = check_rate_limit(
        engine,
        post_type="feed",
        max_feed_per_day=2,
        max_feed_per_week=10,
        max_story_per_day=5,
    )
    assert decision.allowed is False
    assert "paused" in (decision.reason or "").lower()
```

- [ ] **Step 2: Implement `src/ig_qt/publisher/rate_limiter.py`**

```python
"""Pre-publish rate limit checks."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import Engine, func, select

from ig_qt.db import session_scope
from ig_qt.models import IGAccountState, Post


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    reason: str | None


def is_paused(pause_file: Path) -> bool:
    return pause_file.exists()


def is_within_posting_window(
    now_utc: datetime, *, start: int, end: int, tz_offset_hours: int
) -> bool:
    local = now_utc.astimezone(timezone(timedelta(hours=tz_offset_hours)))
    return start <= local.hour < end


def _count_published_since(
    engine: Engine, *, post_type: str, since: datetime
) -> int:
    with session_scope(engine) as s:
        n = (
            s.execute(
                select(func.count())
                .select_from(Post)
                .where(
                    Post.post_type == post_type,
                    Post.status == "published",
                    Post.published_at >= since,
                )
            ).scalar()
            or 0
        )
        return int(n)


def check_rate_limit(
    engine: Engine,
    *,
    post_type: str,
    max_feed_per_day: int,
    max_feed_per_week: int,
    max_story_per_day: int,
) -> RateLimitDecision:
    now = datetime.now(timezone.utc)
    with session_scope(engine) as s:
        state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
    if state and state.pause_until and state.pause_until > now:
        return RateLimitDecision(False, f"account paused until {state.pause_until.isoformat()}")
    if state and state.challenge_pending:
        return RateLimitDecision(False, "challenge pending — manual resolve required")

    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    if post_type == "feed":
        daily = _count_published_since(engine, post_type="feed", since=day_ago)
        if daily >= max_feed_per_day:
            return RateLimitDecision(False, f"feed daily limit reached ({daily}/{max_feed_per_day})")
        weekly = _count_published_since(engine, post_type="feed", since=week_ago)
        if weekly >= max_feed_per_week:
            return RateLimitDecision(
                False, f"feed weekly limit reached ({weekly}/{max_feed_per_week})"
            )
    elif post_type == "story":
        daily = _count_published_since(engine, post_type="story", since=day_ago)
        if daily >= max_story_per_day:
            return RateLimitDecision(False, f"story daily limit reached ({daily}/{max_story_per_day})")
    return RateLimitDecision(True, None)
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/publisher/test_rate_limiter.py -v
uv run mypy --strict src/ig_qt/publisher/rate_limiter.py
git add src/ig_qt/publisher/rate_limiter.py tests/publisher/test_rate_limiter.py
git commit -m "feat(publisher): add rate limiter with daily/weekly caps and pause check"
```

---

## Task 5.3: Skip-day deterministic logic

**Files:**
- Create: `src/ig_qt/publisher/skip_day.py`
- Create: `tests/publisher/test_skip_day.py`

- [ ] **Step 1: Write failing test**

`tests/publisher/test_skip_day.py`:

```python
"""Tests for deterministic skip-day decision."""
from __future__ import annotations

from datetime import date

from ig_qt.publisher.skip_day import should_skip_day


def test_skip_day_deterministic_per_date() -> None:
    d = date(2026, 5, 17)
    a = should_skip_day(d, probability=0.14, seed="seed-1")
    b = should_skip_day(d, probability=0.14, seed="seed-1")
    assert a == b


def test_skip_day_different_seeds_can_differ() -> None:
    d = date(2026, 5, 17)
    # Just check both branches are reachable across seeds
    decisions = {should_skip_day(d, probability=0.5, seed=f"seed-{i}") for i in range(50)}
    assert decisions == {True, False}


def test_skip_day_zero_probability_never_skips() -> None:
    d = date(2026, 5, 17)
    assert should_skip_day(d, probability=0.0, seed="x") is False
```

- [ ] **Step 2: Implement `src/ig_qt/publisher/skip_day.py`**

```python
"""Deterministic skip-day decision: ~14% chance per day, stable per (date, seed)."""
from __future__ import annotations

import hashlib
from datetime import date


def should_skip_day(d: date, *, probability: float, seed: str) -> bool:
    if probability <= 0:
        return False
    if probability >= 1:
        return True
    key = f"{seed}|{d.isoformat()}".encode("utf-8")
    digest = hashlib.sha256(key).digest()
    # Take first 8 bytes as integer, normalize to [0, 1)
    val = int.from_bytes(digest[:8], "big") / (2**64)
    return val < probability
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/publisher/test_skip_day.py -v
uv run mypy --strict src/ig_qt/publisher/skip_day.py
git add src/ig_qt/publisher/skip_day.py tests/publisher/test_skip_day.py
git commit -m "feat(publisher): add deterministic skip-day logic"
```

---

## Task 5.4: instagrapi client wrapper (session persistence)

**Files:**
- Create: `src/ig_qt/publisher/ig_client.py`
- Create: `tests/publisher/test_ig_client.py`

- [ ] **Step 1: Write failing test**

`tests/publisher/test_ig_client.py`:

```python
"""Tests for IGClient (instagrapi wrapper)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ig_qt.publisher.ig_client import IGClient, IGClientError


class _FakeIG:
    """Stand-in for instagrapi.Client."""

    def __init__(self) -> None:
        self.delay_range: list[int] = []
        self.username: str | None = None
        self.password: str | None = None
        self._session: dict[str, Any] | None = None
        self.timeline_calls = 0
        self.feed_uploads: list[tuple[str, str]] = []
        self.story_uploads: list[str] = []
        self.login_attempts = 0

    def load_settings(self, path: Path) -> None:
        self._session = json.loads(Path(path).read_text())

    def dump_settings(self, path: Path) -> None:
        Path(path).write_text(json.dumps({"device": "x"}))

    def login(self, username: str, password: str) -> bool:
        self.login_attempts += 1
        self.username = username
        self.password = password
        return True

    def get_timeline_feed(self) -> dict[str, Any]:
        self.timeline_calls += 1
        return {"feed_items": []}

    def photo_upload(self, path: str, caption: str, **_: Any) -> Any:
        self.feed_uploads.append((path, caption))

        class M:
            pk = "999"

        return M()

    def photo_upload_to_story(self, path: str, **_: Any) -> Any:
        self.story_uploads.append(path)

        class M:
            pk = "888"

        return M()


def test_load_or_login_uses_existing_session(tmp_path: Path) -> None:
    fake = _FakeIG()
    session_path = tmp_path / "session.json"
    session_path.write_text(json.dumps({"device": "y"}))
    client = IGClient(
        fake_factory=lambda: fake,  # type: ignore[arg-type]
        session_path=session_path,
        username="u",
        password="p",
        delay_range=(2, 5),
    )
    client.ensure_logged_in()
    assert fake.login_attempts == 0
    assert fake.timeline_calls == 1


def test_load_or_login_logs_in_when_no_session(tmp_path: Path) -> None:
    fake = _FakeIG()
    session_path = tmp_path / "session.json"
    client = IGClient(
        fake_factory=lambda: fake,  # type: ignore[arg-type]
        session_path=session_path,
        username="u",
        password="p",
        delay_range=(2, 5),
    )
    client.ensure_logged_in()
    assert fake.login_attempts == 1
    assert session_path.exists()


def test_publish_feed_calls_photo_upload(tmp_path: Path) -> None:
    fake = _FakeIG()
    session_path = tmp_path / "s.json"
    session_path.write_text(json.dumps({"device": "z"}))
    client = IGClient(
        fake_factory=lambda: fake,  # type: ignore[arg-type]
        session_path=session_path,
        username="u",
        password="p",
        delay_range=(2, 5),
    )
    client.ensure_logged_in()
    pk = client.publish_feed(asset=Path("a.jpg"), caption="cap")
    assert pk == "999"
    assert fake.feed_uploads == [("a.jpg", "cap")]


def test_publish_story_calls_photo_upload_to_story(tmp_path: Path) -> None:
    fake = _FakeIG()
    session_path = tmp_path / "s.json"
    session_path.write_text(json.dumps({"device": "z"}))
    client = IGClient(
        fake_factory=lambda: fake,  # type: ignore[arg-type]
        session_path=session_path,
        username="u",
        password="p",
        delay_range=(2, 5),
    )
    client.ensure_logged_in()
    pk = client.publish_story(asset=Path("a.jpg"))
    assert pk == "888"
```

- [ ] **Step 2: Implement `src/ig_qt/publisher/ig_client.py`**

```python
"""Thin wrapper around instagrapi with session persistence + safer error mapping."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger


class IGClientError(Exception):
    """Generic publish error."""


class ChallengeRequiredError(IGClientError):
    """IG demands a challenge — manual resolution needed."""


class FeedbackBlockedError(IGClientError):
    """IG soft-block ('action blocked') — back off long."""


class LoginExpiredError(IGClientError):
    """Session expired."""


def _default_factory() -> Any:
    # Imported lazily so tests with --fake-factory don't require instagrapi.
    from instagrapi import Client

    return Client()


class IGClient:
    def __init__(
        self,
        *,
        session_path: Path,
        username: str,
        password: str,
        delay_range: tuple[float, float],
        fake_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._session_path = session_path
        self._username = username
        self._password = password
        self._delay_range = delay_range
        self._factory = fake_factory or _default_factory
        self._cl: Any = None

    def _build_client(self) -> Any:
        cl = self._factory()
        # Some clients accept delay_range as attribute; ignore otherwise.
        try:
            cl.delay_range = list(self._delay_range)
        except AttributeError:
            pass
        return cl

    def ensure_logged_in(self) -> None:
        cl = self._build_client()
        # Try to reuse existing session
        if self._session_path.exists():
            try:
                cl.load_settings(self._session_path)
                # Validate session by lightweight call
                cl.get_timeline_feed()
                self._cl = cl
                logger.info("ig_session_loaded path={}", self._session_path)
                return
            except Exception as exc:
                logger.warning("ig_session_invalid err={}", exc)

        # Fresh login
        try:
            cl.login(self._username, self._password)
            cl.dump_settings(self._session_path)
            self._cl = cl
            logger.info("ig_logged_in_fresh user={}", self._username)
        except Exception as exc:
            self._classify_and_raise(exc)

    def publish_feed(self, *, asset: Path, caption: str) -> str:
        if self._cl is None:
            raise IGClientError("not logged in")
        try:
            media = self._cl.photo_upload(str(asset), caption)
            return str(media.pk)
        except Exception as exc:
            self._classify_and_raise(exc)
            raise  # pragma: no cover

    def publish_story(self, *, asset: Path) -> str:
        if self._cl is None:
            raise IGClientError("not logged in")
        try:
            media = self._cl.photo_upload_to_story(str(asset))
            return str(media.pk)
        except Exception as exc:
            self._classify_and_raise(exc)
            raise  # pragma: no cover

    def warmup(self) -> None:
        """Light-touch read activity prior to publishing."""
        if self._cl is None:
            raise IGClientError("not logged in")
        try:
            self._cl.get_timeline_feed()
        except Exception as exc:
            logger.debug("ig_warmup_soft_fail err={}", exc)

    @staticmethod
    def _classify_and_raise(exc: Exception) -> None:
        # Check by class name so tests don't require instagrapi installed.
        name = type(exc).__name__
        if "Challenge" in name:
            raise ChallengeRequiredError(str(exc)) from exc
        if "Feedback" in name or "PleaseWait" in name or "ActionBlock" in name:
            raise FeedbackBlockedError(str(exc)) from exc
        if "Login" in name:
            raise LoginExpiredError(str(exc)) from exc
        raise IGClientError(str(exc)) from exc
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/publisher/test_ig_client.py -v
uv run mypy --strict src/ig_qt/publisher/ig_client.py
git add src/ig_qt/publisher/ig_client.py tests/publisher/test_ig_client.py
git commit -m "feat(publisher): add IGClient wrapper with session persistence and error mapping"
```

---

## Task 5.5: Pre-warmup helper

**Files:**
- Create: `src/ig_qt/publisher/warmup.py`
- Create: `tests/publisher/test_warmup.py`

- [ ] **Step 1: Write failing test**

`tests/publisher/test_warmup.py`:

```python
"""Tests for pre-publish warmup."""
from __future__ import annotations

import asyncio

import pytest

from ig_qt.publisher.warmup import simulate_pre_publish_activity


class _FakeClient:
    def __init__(self) -> None:
        self.warmup_calls = 0

    def warmup(self) -> None:
        self.warmup_calls += 1


@pytest.mark.asyncio
async def test_warmup_runs_at_least_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    fake = _FakeClient()
    await simulate_pre_publish_activity(fake, sleep_min=0.0, sleep_max=0.0, seed=1)
    assert fake.warmup_calls >= 1
    assert len(sleeps) >= 1
```

- [ ] **Step 2: Implement `src/ig_qt/publisher/warmup.py`**

```python
"""Pre-publish activity simulation: timeline read + randomized sleep."""
from __future__ import annotations

import asyncio
import random
from typing import Protocol


class _SupportsWarmup(Protocol):
    def warmup(self) -> None: ...


async def simulate_pre_publish_activity(
    client: _SupportsWarmup,
    *,
    sleep_min: float = 8.0,
    sleep_max: float = 15.0,
    seed: int | None = None,
) -> None:
    rng = random.Random(seed) if seed is not None else random
    # 1-2 warmup reads with small inter-call delay
    reads = rng.randint(1, 2)
    for _ in range(reads):
        client.warmup()
        await asyncio.sleep(rng.uniform(0.5, 2.0) if sleep_max > 0 else 0)
    await asyncio.sleep(rng.uniform(sleep_min, sleep_max))
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/publisher/test_warmup.py -v
uv run mypy --strict src/ig_qt/publisher/warmup.py
git add src/ig_qt/publisher/warmup.py tests/publisher/test_warmup.py
git commit -m "feat(publisher): add pre-publish activity simulation"
```

---

## Task 5.6: Publisher runner (publish due posts)

**Files:**
- Create: `src/ig_qt/publisher/runner.py`
- Create: `tests/publisher/test_runner.py`

- [ ] **Step 1: Write failing test**

`tests/publisher/test_runner.py`:

```python
"""Tests for publisher runner."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import IGAccountState, Post, PublishLog
from ig_qt.notifier import NoopNotifier
from ig_qt.publisher.ig_client import ChallengeRequiredError, IGClient
from ig_qt.publisher.runner import PublishResult, PublisherRunner


class _FakeClient:
    def __init__(
        self, *, raise_on_feed: Exception | None = None, raise_on_story: Exception | None = None
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
    from PIL import Image
    Image.new("RGB", (1080, 1080), (10, 132, 255)).save(asset, "JPEG")
    now = datetime.now(timezone.utc)
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
    monkeypatch.setattr("ig_qt.publisher.warmup.asyncio.sleep", lambda *_: None)
    summary = await runner.run_due()
    assert summary.published == 1
    assert summary.failed == 0
    with session_scope(engine) as s:
        post = s.query(Post).first()
        assert post.status == "published"
        assert post.ig_media_id == "media-feed"


@pytest.mark.asyncio
async def test_publisher_pauses_on_challenge(seeded: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, _ = seeded
    fake = _FakeClient(raise_on_feed=ChallengeRequiredError("forced"))
    runner = PublisherRunner(
        engine=engine, client=fake, notifier=NoopNotifier(),
        pause_file=Path("/nonexistent/PAUSE"),
        max_feed_per_day=2, max_feed_per_week=10, max_story_per_day=5,
        posting_window_start_hour=0, posting_window_end_hour=24, tz_offset_hours=7,
        skip_day_seed="x", skip_day_probability=0.0, warmup_seed=1,
        sleep_range=(0.0, 0.0),
    )
    monkeypatch.setattr("ig_qt.publisher.warmup.asyncio.sleep", lambda *_: None)
    summary = await runner.run_due()
    assert summary.failed == 1
    with session_scope(engine) as s:
        state = s.query(IGAccountState).first()
        assert state.pause_until is not None
        assert state.challenge_pending is True
        post = s.query(Post).first()
        assert post.status == "failed"


def test_publisher_blocked_by_pause_file(seeded: Any) -> None:
    import asyncio

    engine, _ = seeded
    pause_file = Path("/tmp/igqt_pause_test")
    try:
        pause_file.write_text("")
        fake = _FakeClient()
        runner = PublisherRunner(
            engine=engine, client=fake, notifier=NoopNotifier(),
            pause_file=pause_file,
            max_feed_per_day=2, max_feed_per_week=10, max_story_per_day=5,
            posting_window_start_hour=0, posting_window_end_hour=24, tz_offset_hours=7,
            skip_day_seed="x", skip_day_probability=0.0, warmup_seed=1,
            sleep_range=(0.0, 0.0),
        )
        summary = asyncio.run(runner.run_due())
        assert summary.published == 0
        assert summary.skipped_reason == "pause_file"
    finally:
        if pause_file.exists():
            pause_file.unlink()
```

- [ ] **Step 2: Implement `src/ig_qt/publisher/runner.py`**

```python
"""Publish due posts with anti-ban tactics + structured logging."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

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
        now = datetime.now(timezone.utc)
        if is_paused(self._pause_file):
            logger.info("publisher_skipped reason=pause_file")
            return PublishResult(0, 0, "pause_file")
        if not is_within_posting_window(
            now, start=self._win_start, end=self._win_end, tz_offset_hours=self._tz_offset
        ):
            logger.info("publisher_skipped reason=outside_window")
            return PublishResult(0, 0, "outside_window")

        # Snapshot due posts (snapshot to avoid lock during long upload)
        with session_scope(self._engine) as s:
            posts = list(
                s.execute(
                    select(Post).where(
                        Post.status == "ready", Post.scheduled_for <= now
                    ).order_by(Post.scheduled_for)
                ).scalars()
            )
            for p in posts:
                s.expunge(p)

        if not posts:
            return PublishResult(0, 0, "no_due_posts")

        # If skip-day decision says skip, we don't process feed posts but still process stories.
        skip_today = should_skip_day(
            now.date(), probability=self._skip_prob, seed=self._skip_seed
        )

        published = 0
        failed = 0

        # Login once for the batch
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
                break  # Stop batch on challenge
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
                await self._notifier.send(f"⚠️ ig-qt: session expired — re-login required")
                failed += 1
                break
            except IGClientError as exc:
                self._mark_failed(post.id, "ig_error", str(exc))
                failed += 1
                # Continue to next post; transient errors shouldn't block batch
            except Exception as exc:
                self._mark_failed(post.id, "unexpected", str(exc))
                logger.exception("publisher_unexpected_error post_id={}", post.id)
                failed += 1

        logger.info("publisher_run_done published={} failed={}", published, failed)
        return PublishResult(published=published, failed=failed)

    def _mark_published(self, post_id: int, pk: str, took_ms: int) -> None:
        now = datetime.now(timezone.utc)
        with session_scope(self._engine) as s:
            post = s.execute(select(Post).where(Post.id == post_id)).scalar_one()
            post.status = "published"
            post.ig_media_id = pk
            post.published_at = now
            s.add(
                PublishLog(
                    post_id=post_id, ig_media_id=pk, attempt_no=1,
                    status="success", took_ms=took_ms,
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
                    post_id=post_id, attempt_no=1, status="failed",
                    error_type=error_type, error_message=error_message[:2000],
                )
            )

    def _set_pause(self, duration: timedelta, *, challenge: bool = False) -> None:
        with session_scope(self._engine) as s:
            state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
            if state is None:
                return
            state.pause_until = datetime.now(timezone.utc) + duration
            if challenge:
                state.challenge_pending = True
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/publisher/test_runner.py -v
uv run mypy --strict src/ig_qt/publisher/runner.py
git add src/ig_qt/publisher/runner.py tests/publisher/test_runner.py
git commit -m "feat(publisher): add publish runner with anti-ban tactics"
```

---

## Task 5.7: Story builders runtime (event reminder + market recap)

**Files:**
- Create: `src/ig_qt/stories_runtime.py`
- Create: `tests/test_stories_runtime.py`

This module bridges story builders (M4 `composer/stories.py`) → renders → publishes, without going through PostDraft. Used for scheduled daily story jobs.

- [ ] **Step 1: Write failing test**

`tests/test_stories_runtime.py`:

```python
"""Tests for stories_runtime."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Event, IGAccountState, Post, PriceCache
from ig_qt.notifier import NoopNotifier
from ig_qt.publisher.runner import PublisherRunner
from ig_qt.stories_runtime import generate_event_reminder_story, generate_market_recap_story


class _FakeClient:
    def ensure_logged_in(self) -> None: ...
    def warmup(self) -> None: ...
    def publish_feed(self, *, asset: Path, caption: str) -> str: return "x"
    def publish_story(self, *, asset: Path) -> str: return "story-pk"


@pytest.fixture
def engine_path(tmp_path: Path) -> Any:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    return engine, tmp_path


@pytest.mark.asyncio
async def test_generate_event_reminder_story_inserts_post(engine_path: Any) -> None:
    engine, tmp_path = engine_path
    now = datetime.now(timezone.utc)
    with session_scope(engine) as s:
        s.add(
            Event(
                source="ff", event_time=now + timedelta(hours=2),
                country="US", currency="USD", name="CPI", impact="high",
                forecast="0.3%", previous="0.4%", actual=None, dedup_key="e1",
            )
        )

    post_id = await generate_event_reminder_story(
        engine=engine, data_dir=tmp_path, logo_path=tmp_path / "logo.png",
        handle="@x", scheduled_for=now,
    )
    assert post_id is not None

    with session_scope(engine) as s:
        post = s.query(Post).filter(Post.id == post_id).one()
        assert post.post_type == "story"
        assert post.status == "ready"
        assert Path(post.asset_path).exists()
```

- [ ] **Step 2: Implement `src/ig_qt/stories_runtime.py`**

```python
"""Generate scheduled story posts (event reminder, market recap) without LLM."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.composer.html_renderer import render_card
from ig_qt.composer.postprocess import finalize_story_image
from ig_qt.composer.stories import (
    build_event_reminder_context,
    build_market_recap_context,
)
from ig_qt.db import session_scope
from ig_qt.models import Event, Post, PriceCache


async def _render_and_persist(
    *,
    engine: Engine,
    template: str,
    context: dict[str, Any],
    caption: str,
    visual_type: str,
    data_dir: Path,
    logo_path: Path,
    handle: str,
    scheduled_for: datetime,
) -> int | None:
    # Reserve a post id by inserting placeholder
    with session_scope(engine) as s:
        placeholder = Post(
            post_type="story",
            caption_final=caption,
            hashtags=[],
            asset_path="pending",
            visual_type=visual_type,
            scheduled_for=scheduled_for,
            status="ready",
        )
        s.add(placeholder)
        s.flush()
        post_id = placeholder.id

    out_dir = data_dir / "posts" / str(post_id)
    raw = out_dir / "raw.png"
    final = out_dir / "story.jpg"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        await render_card(
            template=template,
            context={**context, "handle": handle, "orientation": "story"},
            out_path=raw,
            viewport=(1080, 1920),
        )
        finalize_story_image(src=raw, dst=final, logo_path=logo_path, handle=handle)
    except Exception as exc:
        logger.error("story_render_failed template={} err={}", template, exc)
        with session_scope(engine) as s:
            p = s.execute(select(Post).where(Post.id == post_id)).scalar_one()
            p.status = "failed"
            p.error_log = str(exc)
        return None

    with session_scope(engine) as s:
        p = s.execute(select(Post).where(Post.id == post_id)).scalar_one()
        p.asset_path = str(final)
    return post_id


async def generate_event_reminder_story(
    *,
    engine: Engine,
    data_dir: Path,
    logo_path: Path,
    handle: str,
    scheduled_for: datetime,
    window_hours: int = 12,
) -> int | None:
    now = datetime.now(timezone.utc)
    with session_scope(engine) as s:
        events = list(
            s.execute(select(Event).order_by(Event.event_time)).scalars()
        )
    ctx = build_event_reminder_context(events=events, now=now, window_hours=window_hours)
    if not ctx["events"]:
        logger.info("event_reminder_no_events")
        return None
    caption = (
        "Event macro penting hari ini. Watch volatilitas di sekitar window time. "
        "💬 Mana yang paling kamu pantau?"
    )
    return await _render_and_persist(
        engine=engine, template="event_card.html", context=ctx,
        caption=caption, visual_type="event",
        data_dir=data_dir, logo_path=logo_path, handle=handle,
        scheduled_for=scheduled_for,
    )


async def generate_market_recap_story(
    *,
    engine: Engine,
    data_dir: Path,
    logo_path: Path,
    handle: str,
    scheduled_for: datetime,
    symbols: list[str],
) -> int | None:
    with session_scope(engine) as s:
        rows = list(s.execute(select(PriceCache)).scalars())
    latest_per_symbol: dict[str, list[dict[str, Any]]] = {}
    latest_fetched: dict[str, datetime] = {}
    for r in rows:
        if r.symbol not in symbols:
            continue
        prev = latest_fetched.get(r.symbol)
        if prev is None or r.fetched_at > prev:
            latest_per_symbol[r.symbol] = list(r.ohlc_json)
            latest_fetched[r.symbol] = r.fetched_at
    ctx = build_market_recap_context(latest_prices=latest_per_symbol, symbols=symbols)
    if not ctx["recaps"]:
        logger.info("market_recap_no_data")
        return None
    caption = (
        "Recap harian pair major. Closing vs previous close. 💬 Pair mana yang paling "
        "kamu watch besok?"
    )
    return await _render_and_persist(
        engine=engine, template="market_recap.html", context=ctx,
        caption=caption, visual_type="recap",
        data_dir=data_dir, logo_path=logo_path, handle=handle,
        scheduled_for=scheduled_for,
    )
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/test_stories_runtime.py -v
uv run mypy --strict src/ig_qt/stories_runtime.py
git add src/ig_qt/stories_runtime.py tests/test_stories_runtime.py
git commit -m "feat(stories): add scheduled event reminder and market recap generators"
```

---

## Task 5.8: APScheduler wiring

**Files:**
- Create: `src/ig_qt/scheduler.py`
- Create: `tests/test_scheduler.py`
- Modify: `src/ig_qt/app.py`, `src/ig_qt/__main__.py`

- [ ] **Step 1: Write failing test (config-only, no scheduler start)**

`tests/test_scheduler.py`:

```python
"""Tests for scheduler config building."""
from __future__ import annotations

from pathlib import Path

import yaml

from ig_qt.config import load_config
from ig_qt.scheduler import build_jobs_spec


def test_build_jobs_spec_includes_all_required(tmp_path: Path) -> None:
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "brand": {"primary": "#0", "accent": "#0", "font": "Inter",
                          "handle": "@x", "logo_path": "assets/logo.png"},
                "llm": {"provider": "router_9", "base_url_env": "L_B", "api_key_env": "L_K",
                        "models": {"ranker": "r", "composer": "c"},
                        "request_timeout_seconds": 30, "max_retries": 2},
                "schedule": {"timezone": "Asia/Jakarta", "feed_post_hour": 11,
                             "feed_post_jitter_minutes": 15, "story_event_hour": 12,
                             "story_recap_hour": 21, "skip_day_probability": 0.14,
                             "posting_window_start_hour": 6, "posting_window_end_hour": 23},
                "ig": {"username_env": "U", "password_env": "P", "max_feed_per_day": 2,
                       "max_feed_per_week": 10, "max_story_per_day": 5,
                       "max_login_per_day": 1, "delay_range_seconds": [2, 5]},
                "collector": {"news_api_enabled": False, "news_api_key_env": "NA",
                              "gnews_enabled": False, "gnews_key_env": "GN",
                              "twelve_data_enabled": False, "twelve_data_key_env": "TD",
                              "forex_factory_enabled": False, "symbols": []},
                "notifier": {"telegram_enabled": False, "telegram_bot_token_env": "T",
                             "telegram_chat_id_env": "TC"},
                "paths": {"data_dir_env": "DD", "data_dir_default": str(tmp_path)},
            }
        )
    )
    import os
    os.environ.update({"L_B": "x", "L_K": "x", "U": "u", "P": "p"})
    cfg = load_config(cfg_path)
    spec = build_jobs_spec(cfg)
    job_ids = {j["id"] for j in spec}
    assert "collect_news_morning" in job_ids
    assert "collect_news_evening" in job_ids
    assert "ff_calendar_weekly" in job_ids
    assert "analyst_daily" in job_ids
    assert "composer_loop" in job_ids
    assert "publisher_loop" in job_ids
    assert "story_event_reminder" in job_ids
    assert "story_market_recap" in job_ids
```

- [ ] **Step 2: Implement `src/ig_qt/scheduler.py`**

```python
"""APScheduler setup with persistent SQLite jobstore."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from ig_qt.config import AppConfig


def build_jobs_spec(cfg: AppConfig) -> list[dict[str, Any]]:
    """Pure function: returns the job spec table without scheduling.

    Useful for tests + observability /jobs endpoint.
    """
    sched = cfg.schedule
    return [
        {
            "id": "collect_news_morning",
            "trigger": CronTrigger(hour=9, jitter=900, timezone=sched.timezone),
        },
        {
            "id": "collect_news_evening",
            "trigger": CronTrigger(hour=18, jitter=900, timezone=sched.timezone),
        },
        {
            "id": "ff_calendar_weekly",
            "trigger": CronTrigger(
                day_of_week="mon", hour=7, jitter=1800, timezone=sched.timezone
            ),
        },
        {
            "id": "analyst_daily",
            "trigger": CronTrigger(
                hour=sched.feed_post_hour, minute=0,
                jitter=sched.feed_post_jitter_minutes * 60,
                timezone=sched.timezone,
            ),
        },
        {
            "id": "composer_loop",
            "trigger": IntervalTrigger(minutes=15),
        },
        {
            "id": "publisher_loop",
            "trigger": IntervalTrigger(minutes=5),
        },
        {
            "id": "story_event_reminder",
            "trigger": CronTrigger(
                hour=sched.story_event_hour, jitter=600, timezone=sched.timezone
            ),
        },
        {
            "id": "story_market_recap",
            "trigger": CronTrigger(
                hour=sched.story_recap_hour, jitter=900, timezone=sched.timezone
            ),
        },
    ]


def build_scheduler(*, cfg: AppConfig, jobs_db: Path) -> AsyncIOScheduler:
    jobs_db.parent.mkdir(parents=True, exist_ok=True)
    scheduler = AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{jobs_db}")},
        timezone=cfg.schedule.timezone,
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 600},
    )
    return scheduler


def attach_jobs(
    scheduler: AsyncIOScheduler,
    *,
    cfg: AppConfig,
    handlers: dict[str, Callable[[], Any]],
) -> None:
    """Attach handler functions to job ids. `handlers` keys must match job ids."""
    spec = build_jobs_spec(cfg)
    for job in spec:
        handler = handlers.get(job["id"])
        if handler is None:
            logger.warning("scheduler_no_handler job_id={}", job["id"])
            continue
        scheduler.add_job(
            handler, trigger=job["trigger"], id=job["id"], replace_existing=True
        )
        logger.info("scheduler_job_attached id={} trigger={}", job["id"], job["trigger"])
```

- [ ] **Step 3: Wire `run` subcommand in `app.py`**

Append:

```python
async def run_long_running(*, config_path: Path) -> int:
    """Long-running orchestrator: APScheduler + handlers wired together."""
    import asyncio
    from datetime import datetime, timedelta, timezone

    from ig_qt.analyst.runner import AnalystRunner
    from ig_qt.collector.pipeline import build_pipeline_from_config
    from ig_qt.composer.runner import ComposerRunner
    from ig_qt.publisher.ig_client import IGClient
    from ig_qt.publisher.runner import PublisherRunner
    from ig_qt.scheduler import attach_jobs, build_scheduler
    from ig_qt.stories_runtime import (
        generate_event_reminder_story,
        generate_market_recap_story,
    )

    cfg = load_config(config_path)
    log_dir = cfg.paths.data_dir / "logs"
    configure_logging(log_dir=log_dir, level="INFO", json_logs=True)
    engine = build_engine(cfg.paths.data_dir / "ig_qt.db")
    init_schema(engine)
    notifier = build_notifier(
        enabled=cfg.notifier.telegram_enabled,
        bot_token=(
            cfg.notifier.telegram_bot_token.get_secret_value()
            if cfg.notifier.telegram_bot_token
            else None
        ),
        chat_id=cfg.notifier.telegram_chat_id,
    )

    provider = build_llm_provider(cfg.llm)
    analyst = AnalystRunner(
        engine=engine, provider=provider,
        ranker_model=cfg.llm.ranker_model,
        composer_model=cfg.llm.composer_model,
    )
    composer = ComposerRunner(
        engine=engine,
        data_dir=cfg.paths.data_dir,
        logo_path=Path(cfg.brand.logo_path),
        handle=cfg.brand.handle,
        scheduled_for_factory=lambda d: datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    ig_client = IGClient(
        session_path=cfg.paths.data_dir / "ig_session.json",
        username=cfg.ig.username,
        password=cfg.ig.password.get_secret_value(),
        delay_range=cfg.ig.delay_range_seconds,
    )
    publisher = PublisherRunner(
        engine=engine,
        client=ig_client,
        notifier=notifier,
        pause_file=cfg.paths.data_dir / "PAUSE",
        max_feed_per_day=cfg.ig.max_feed_per_day,
        max_feed_per_week=cfg.ig.max_feed_per_week,
        max_story_per_day=cfg.ig.max_story_per_day,
        posting_window_start_hour=cfg.schedule.posting_window_start_hour,
        posting_window_end_hour=cfg.schedule.posting_window_end_hour,
        tz_offset_hours=7,  # WIB
        skip_day_seed=cfg.ig.username,
        skip_day_probability=cfg.schedule.skip_day_probability,
        warmup_seed=42,
    )

    pipeline = build_pipeline_from_config(engine, cfg)

    async def collect_news() -> None:
        await pipeline.run_once()

    async def collect_calendar() -> None:
        # Same pipeline; events fetched via Forex Factory source
        await pipeline.run_once()

    async def analyst_job() -> None:
        await analyst.run_once(today=datetime.now(timezone.utc))

    async def composer_job() -> None:
        await composer.run_once()

    async def publisher_job() -> None:
        await publisher.run_due()

    async def story_event_job() -> None:
        await generate_event_reminder_story(
            engine=engine, data_dir=cfg.paths.data_dir,
            logo_path=Path(cfg.brand.logo_path),
            handle=cfg.brand.handle,
            scheduled_for=datetime.now(timezone.utc),
        )

    async def story_recap_job() -> None:
        await generate_market_recap_story(
            engine=engine, data_dir=cfg.paths.data_dir,
            logo_path=Path(cfg.brand.logo_path),
            handle=cfg.brand.handle,
            scheduled_for=datetime.now(timezone.utc),
            symbols=cfg.collector.symbols,
        )

    handlers = {
        "collect_news_morning": collect_news,
        "collect_news_evening": collect_news,
        "ff_calendar_weekly": collect_calendar,
        "analyst_daily": analyst_job,
        "composer_loop": composer_job,
        "publisher_loop": publisher_job,
        "story_event_reminder": story_event_job,
        "story_market_recap": story_recap_job,
    }

    scheduler = build_scheduler(cfg=cfg, jobs_db=cfg.paths.data_dir / "jobs.db")
    attach_jobs(scheduler, cfg=cfg, handlers=handlers)
    scheduler.start()
    logger.info("scheduler_started")

    # Block forever
    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=True)
    return 0
```

In `__main__.py` add:

```python
sub.add_parser("run", help="Run scheduler (long-running)")
# ...
if args.cmd == "run":
    return asyncio.run(run_long_running(config_path=args.config))
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_scheduler.py -v
uv run mypy --strict src/ig_qt/scheduler.py src/ig_qt/app.py src/ig_qt/__main__.py
git add src/ig_qt/scheduler.py src/ig_qt/app.py src/ig_qt/__main__.py tests/test_scheduler.py
git commit -m "feat(scheduler): wire APScheduler with persistent jobstore + run command"
```

---

## Task 5.9: First-time IG login script

**Files:**
- Create: `scripts/ig_login_first_time.py`

- [ ] **Step 1: Implement script**

```python
"""Interactive first-time IG login. Handles ChallengeRequired (email/SMS code).

Usage:
    uv run python scripts/ig_login_first_time.py

Reads username/password from .env (IG_USERNAME / IG_PASSWORD).
Prompts for verification code if Instagram requests it.
Saves session to data/ig_session.json.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger


def main() -> int:
    try:
        from instagrapi import Client  # type: ignore[import-not-found]
        from instagrapi.exceptions import ChallengeRequired  # type: ignore[import-not-found]
    except ImportError as exc:
        print(f"instagrapi not installed: {exc}")
        return 1

    username = os.environ.get("IG_USERNAME")
    password = os.environ.get("IG_PASSWORD")
    if not username or not password:
        print("Set IG_USERNAME and IG_PASSWORD in .env first.")
        return 2

    data_dir = Path(os.environ.get("IG_QT_DATA_DIR", "data"))
    session_path = data_dir / "ig_session.json"
    backups_dir = data_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    cl = Client()
    cl.delay_range = [2, 5]

    def challenge_code_handler(_username: str, _choice: str) -> str:
        return input("Enter verification code from email/SMS: ").strip()

    cl.challenge_code_handler = challenge_code_handler

    try:
        cl.login(username, password)
    except ChallengeRequired:
        print("Challenge required, follow prompts...")
        cl.challenge_resolve(cl.last_json)
        cl.login(username, password)

    session_path.parent.mkdir(parents=True, exist_ok=True)
    cl.dump_settings(session_path)
    from datetime import datetime
    backup_path = backups_dir / f"ig_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup_path.write_text(session_path.read_text())
    logger.info("first_time_login_done session_path={} backup={}", session_path, backup_path)
    print(f"Session saved to {session_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add scripts/ig_login_first_time.py
git commit -m "feat(scripts): add first-time IG login with challenge handling"
```

---

## M5 Acceptance Criteria

- [ ] All `tests/publisher/*` and `tests/test_scheduler.py` green
- [ ] `mypy --strict src/ig_qt/publisher/ src/ig_qt/scheduler.py src/ig_qt/stories_runtime.py` clean
- [ ] `python -m ig_qt run` starts scheduler and exits cleanly on Ctrl+C
- [ ] `data/PAUSE` file blocks publisher during run (verified via log)
- [ ] Skip-day deterministic: same date+seed produces same boolean across runs
- [ ] ChallengeRequired sets `pause_until = now + 7d` and `challenge_pending = true`; Telegram alert sent
- [ ] FeedbackBlockedError sets `pause_until = now + 24h`; Telegram alert sent
- [ ] First-time login script saves valid session.json and backup copy
- [ ] No publisher attempt outside posting window (06:00–23:00 WIB by default)

## M5 Self-Review Notes

- **Why expunge posts before publish loop:** instagrapi uploads can take 30+ seconds. Holding a SQLAlchemy session open the entire time risks lock contention with composer/analyst running simultaneously. Snapshot + per-result tiny sessions = correct.
- **Why break batch on Challenge/Feedback/LoginExpired:** these are account-level signals. Continuing to publish after one of them gets the account flagged faster. Hard stop, alert human.
- **Why `last_post_at` updated optimistically:** even if next post fails, this stops "rapid retry" patterns that look like bots.
- **Skip-day fairness:** seed-based hash means stable per (account, date). Different accounts with different `skip_day_seed` get different schedules — important if account is restored from backup.
- **Posting window WIB-aware:** `tz_offset_hours=7` hardcoded for WIB. If the scheduler timezone changes in config, update this. (Or: derive from config — left as small refactor opportunity for M7.)
- **`build_jobs_spec` is pure:** facilitates the M6 `/health` endpoint that lists scheduled jobs.
- **Tests use `_FakeClient` not real instagrapi:** tests must run on machine without IG creds. The runner only needs `_PubClient` Protocol.
- **No retries inside publisher for hard errors:** Challenge/Feedback have multi-day pause. Soft network errors trickle to outer scheduler retry on next interval (every 5 min).
