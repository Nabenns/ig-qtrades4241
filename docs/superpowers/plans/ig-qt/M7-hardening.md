# M7 Hardening — Implementation Plan

> **Parent:** [`../2026-05-17-ig-forex-automation.md`](../2026-05-17-ig-forex-automation.md)
> **Prereq:** M1–M6 complete and deployed.

**Goal:** Operational hardening after first deployment. Add account warm-up phase support, observability tuning, content quality safeguards, and small QoL improvements that emerged during real-world running. Each task here is independent and optional — pick what's needed based on what you observe in the first 1-2 weeks of running.

**Files created in M7:**
- `src/ig_qt/admin/` — small CLI helpers for ops
- `tests/admin/test_*.py`
- `src/ig_qt/audit.py` — periodic content audit job
- `tests/test_audit.py`
- `src/ig_qt/analyst/prompts/ranker.v2.md`, `composer.v2.md` (only if v1 needs improvement)
- Modify: `src/ig_qt/__main__.py` (admin subcommands)

---

## Task 7.1: Warm-up mode (manual posting period before automation)

**Files:**
- Create: `src/ig_qt/admin/__init__.py`
- Create: `src/ig_qt/admin/warmup_mode.py`
- Create: `tests/admin/__init__.py`
- Create: `tests/admin/test_warmup_mode.py`
- Modify: `src/ig_qt/__main__.py`

**Depends on:** OD-2 (new vs existing IG account). Skip this task entirely if account is already 30+ days old with regular activity.

**Concept:** For new accounts, IG flags rapid bot-like behavior. The standard mitigation is a 1-2 week warm-up where you post manually via the app (3-5 manual posts, follow some accounts, react to stories), THEN start the bot. This task adds two CLI helpers:

1. `python -m ig_qt admin warmup-status` — prints account age, recent activity, and warm-up readiness assessment.
2. `python -m ig_qt admin warmup-enable` / `warmup-disable` — toggles a flag in `ig_account_state` that publisher checks.

- [ ] **Step 1: Add warmup flag to `IGAccountState`**

In `src/ig_qt/models.py`, add:

```python
    warmup_active: Mapped[bool] = mapped_column(Boolean, default=False)
    warmup_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Note: requires schema migration. For SQLite the cheapest path is a manual `ALTER TABLE`:

```bash
docker compose exec ig-qt sqlite3 /app/data/ig_qt.db \
  "ALTER TABLE ig_account_state ADD COLUMN warmup_active BOOLEAN DEFAULT 0"
docker compose exec ig-qt sqlite3 /app/data/ig_qt.db \
  "ALTER TABLE ig_account_state ADD COLUMN warmup_started_at DATETIME"
```

(Switch to Alembic if/when M7 grows more migrations — for now manual ALTER is fine.)

- [ ] **Step 2: Update `PublisherRunner` to respect warmup flag**

In `src/ig_qt/publisher/runner.py`, in `run_due` after `is_within_posting_window` check:

```python
        with session_scope(self._engine) as s:
            state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
            if state and state.warmup_active:
                logger.info("publisher_skipped reason=warmup_active")
                return PublishResult(0, 0, "warmup_active")
```

- [ ] **Step 3: Write failing test**

`tests/admin/test_warmup_mode.py`:

```python
"""Tests for warmup mode admin helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ig_qt.admin.warmup_mode import (
    WarmupStatus,
    assess_readiness,
    disable_warmup,
    enable_warmup,
)
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import IGAccountState


def test_enable_then_disable(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    with session_scope(engine) as s:
        s.add(IGAccountState(username="u"))

    enable_warmup(engine)
    with session_scope(engine) as s:
        state = s.query(IGAccountState).first()
        assert state.warmup_active is True
        assert state.warmup_started_at is not None

    disable_warmup(engine)
    with session_scope(engine) as s:
        state = s.query(IGAccountState).first()
        assert state.warmup_active is False


def test_assess_readiness_returns_warmup_active() -> None:
    state = IGAccountState(
        username="u",
        warmup_active=True,
        warmup_started_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    status = assess_readiness(state, now=datetime(2026, 5, 15, tzinfo=timezone.utc))
    assert isinstance(status, WarmupStatus)
    assert status.warmup_active is True
    assert status.days_in_warmup >= 14
```

- [ ] **Step 4: Implement `src/ig_qt/admin/__init__.py`** (empty)

- [ ] **Step 5: Implement `src/ig_qt/admin/warmup_mode.py`**

```python
"""Warmup mode admin helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.db import session_scope
from ig_qt.models import IGAccountState


@dataclass(frozen=True, slots=True)
class WarmupStatus:
    warmup_active: bool
    warmup_started_at: datetime | None
    days_in_warmup: int
    last_post_at: datetime | None


def enable_warmup(engine: Engine) -> None:
    with session_scope(engine) as s:
        state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
        if state is None:
            state = IGAccountState(username="unknown")
            s.add(state)
            s.flush()
        state.warmup_active = True
        state.warmup_started_at = datetime.now(timezone.utc)
    logger.info("warmup_enabled")


def disable_warmup(engine: Engine) -> None:
    with session_scope(engine) as s:
        state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
        if state is None:
            return
        state.warmup_active = False
    logger.info("warmup_disabled")


def assess_readiness(state: IGAccountState, *, now: datetime) -> WarmupStatus:
    if state.warmup_started_at is not None:
        days = max(0, (now - state.warmup_started_at).days)
    else:
        days = 0
    return WarmupStatus(
        warmup_active=bool(state.warmup_active),
        warmup_started_at=state.warmup_started_at,
        days_in_warmup=days,
        last_post_at=state.last_post_at,
    )
```

- [ ] **Step 6: Wire `admin warmup-*` subcommands**

In `src/ig_qt/__main__.py` extend the parser:

```python
admin = sub.add_parser("admin", help="Operational admin commands")
admin_sub = admin.add_subparsers(dest="admin_cmd")
admin_sub.add_parser("warmup-status", help="Show warmup state")
admin_sub.add_parser("warmup-enable", help="Pause publisher and start warmup window")
admin_sub.add_parser("warmup-disable", help="End warmup, resume publisher")
```

Dispatch:

```python
if args.cmd == "admin":
    return run_admin(config_path=args.config, admin_cmd=args.admin_cmd)
```

In `src/ig_qt/app.py`:

```python
def run_admin(*, config_path: Path, admin_cmd: str | None) -> int:
    from datetime import datetime, timezone

    from ig_qt.admin.warmup_mode import (
        assess_readiness,
        disable_warmup,
        enable_warmup,
    )
    from sqlalchemy import select
    from ig_qt.models import IGAccountState

    cfg = load_config(config_path)
    configure_logging(log_dir=cfg.paths.data_dir / "logs", level="INFO", json_logs=False)
    engine = build_engine(cfg.paths.data_dir / "ig_qt.db")
    init_schema(engine)

    if admin_cmd == "warmup-enable":
        enable_warmup(engine)
        print("Warmup enabled. Publisher will skip until you run warmup-disable.")
        return 0
    if admin_cmd == "warmup-disable":
        disable_warmup(engine)
        print("Warmup disabled. Publisher will resume on next tick.")
        return 0
    if admin_cmd == "warmup-status":
        with session_scope(engine) as s:
            state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
        if state is None:
            print("No account state row yet — run --check or any pipeline first.")
            return 1
        status = assess_readiness(state, now=datetime.now(timezone.utc))
        print(f"warmup_active:    {status.warmup_active}")
        print(f"warmup_started:   {status.warmup_started_at}")
        print(f"days_in_warmup:   {status.days_in_warmup}")
        print(f"last_post_at:     {status.last_post_at}")
        if status.warmup_active and status.days_in_warmup >= 14:
            print("✅ Recommend running: admin warmup-disable")
        elif status.warmup_active:
            print(f"⏳ Continue warmup ({14 - status.days_in_warmup} days remaining)")
        return 0
    print("Unknown admin command. Try: warmup-status, warmup-enable, warmup-disable")
    return 2
```

- [ ] **Step 7: Run + commit**

```bash
uv run pytest tests/admin -v
uv run mypy --strict src/ig_qt/admin/ src/ig_qt/app.py src/ig_qt/__main__.py
git add src/ig_qt/admin/ src/ig_qt/models.py src/ig_qt/publisher/runner.py src/ig_qt/app.py src/ig_qt/__main__.py tests/admin/
git commit -m "feat(admin): add warmup mode with publisher gating and CLI helpers"
```

---

## Task 7.2: Periodic content audit (numerical accuracy + tone)

**Files:**
- Create: `src/ig_qt/audit.py`
- Create: `tests/test_audit.py`

**Concept:** Run a weekly audit query that flags published posts with potential issues for human review. Examples:
- Caption mentions a price that's not in `prices_cache` for the same date.
- Caption uses banned phrases ("guaranteed", "pasti naik", "BUY", "SELL" without context).
- Confidence stored < 0.7 (was published anyway because passed at compose time).

Outputs flagged post IDs as a Telegram message + a `data/logs/audit-<date>.json` report.

- [ ] **Step 1: Write failing test**

`tests/test_audit.py`:

```python
"""Tests for content audit."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ig_qt.audit import audit_recent_posts
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Post, PostDraft


def _seed_published_post(engine: Any, *, caption: str, confidence: float = 0.85) -> int:
    with session_scope(engine) as s:
        draft = PostDraft(
            post_type="feed", source_news_ids=[], topic_tag="t",
            angle="a", key_points=["a"], caption_draft=caption,
            visual_spec={"type": "headline", "headline": "x"},
            disclaimer_required=False, confidence=confidence,
            llm_provider="m", llm_model="m", prompt_version="v1",
            status="consumed",
        )
        s.add(draft)
        s.flush()
        post = Post(
            draft_id=draft.id, post_type="feed", caption_final=caption, hashtags=[],
            asset_path="x", visual_type="headline",
            scheduled_for=datetime.now(timezone.utc),
            published_at=datetime.now(timezone.utc),
            status="published", ig_media_id="x",
        )
        s.add(post)
        s.flush()
        return post.id


def test_audit_flags_banned_phrase(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    pid = _seed_published_post(
        engine, caption="Pasti naik. BUY EUR/USD sekarang!"
    )
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
        engine, caption="FOMC minutes hawkish. Watch USD/JPY level 158.", confidence=0.85
    )
    flags = audit_recent_posts(engine, days=7)
    assert pid not in {f.post_id for f in flags}
```

- [ ] **Step 2: Implement `src/ig_qt/audit.py`**

```python
"""Periodic content audit: flag published posts for human review."""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.db import session_scope
from ig_qt.models import Post, PostDraft

_BANNED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bpasti\s+(naik|turun)\b", re.IGNORECASE),
    re.compile(r"\bguaranteed?\s+(profit|gain|win)\b", re.IGNORECASE),
    re.compile(r"\b(BUY|SELL)\s+[A-Z]{3}/?[A-Z]{3}", re.IGNORECASE),
    re.compile(r"\bsignal\s+pasti\b", re.IGNORECASE),
    re.compile(r"\bdijamin\s+(naik|untung|profit)\b", re.IGNORECASE),
)

_LOW_CONFIDENCE = 0.7


@dataclass(frozen=True, slots=True)
class AuditFlag:
    post_id: int
    reason: str
    excerpt: str


def _check_banned_phrase(caption: str) -> str | None:
    for pat in _BANNED_PATTERNS:
        m = pat.search(caption)
        if m:
            return m.group(0)
    return None


def audit_recent_posts(engine: Engine, *, days: int = 7) -> list[AuditFlag]:
    """Audit posts published within the last `days` days. Returns flagged items."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    flags: list[AuditFlag] = []

    with session_scope(engine) as s:
        rows = list(
            s.execute(
                select(Post, PostDraft)
                .outerjoin(PostDraft, Post.draft_id == PostDraft.id)
                .where(Post.status == "published", Post.published_at >= cutoff)
            )
        )

    for post, draft in rows:
        cap = post.caption_final or ""
        banned = _check_banned_phrase(cap)
        if banned:
            flags.append(
                AuditFlag(
                    post_id=post.id,
                    reason=f"banned_phrase:{banned!r}",
                    excerpt=cap[:160],
                )
            )
            continue
        if draft is not None and draft.confidence < _LOW_CONFIDENCE:
            flags.append(
                AuditFlag(
                    post_id=post.id,
                    reason=f"low_confidence:{draft.confidence:.2f}",
                    excerpt=cap[:160],
                )
            )

    logger.info("audit_done flagged={} window_days={}", len(flags), days)
    return flags


def format_audit_report(flags: Sequence[AuditFlag]) -> str:
    if not flags:
        return "✅ ig-qt audit: no flags this week."
    lines = [f"⚠️ ig-qt audit: {len(flags)} flagged post(s):"]
    for f in flags[:20]:
        lines.append(f"  • #{f.post_id}: {f.reason}")
        lines.append(f"    > {f.excerpt}")
    if len(flags) > 20:
        lines.append(f"  ...and {len(flags) - 20} more.")
    return "\n".join(lines)
```

- [ ] **Step 3: Add weekly audit to scheduler**

In `src/ig_qt/scheduler.py`, append to `build_jobs_spec`:

```python
        {
            "id": "weekly_audit",
            "trigger": CronTrigger(
                day_of_week="sun", hour=22, jitter=600, timezone=sched.timezone
            ),
        },
```

In `src/ig_qt/app.py` `run_long_running`, add handler:

```python
    async def audit_job() -> None:
        from ig_qt.audit import audit_recent_posts, format_audit_report
        flags = audit_recent_posts(engine, days=7)
        report = format_audit_report(flags)
        await notifier.send(report)

    handlers["weekly_audit"] = audit_job
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_audit.py -v
uv run mypy --strict src/ig_qt/audit.py src/ig_qt/scheduler.py src/ig_qt/app.py
git add src/ig_qt/audit.py src/ig_qt/scheduler.py src/ig_qt/app.py tests/test_audit.py
git commit -m "feat(audit): add weekly content audit with banned-phrase + confidence checks"
```

---

## Task 7.3: Asset cleanup job (storage hygiene)

**Files:**
- Create: `src/ig_qt/admin/cleanup.py`
- Create: `tests/admin/test_cleanup.py`

**Concept:** `data/posts/<id>/raw.png` files accumulate. Once `posts.status='published'`, the raw image isn't needed. Run weekly cleanup that deletes raw + intermediate files older than 30 days for published posts. Keep final `feed.jpg` / `story.jpg` for audit reference.

- [ ] **Step 1: Write failing test**

`tests/admin/test_cleanup.py`:

```python
"""Tests for asset cleanup."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

    old_time = datetime.now(timezone.utc) - timedelta(days=45)
    new_time = datetime.now(timezone.utc) - timedelta(days=2)
    with session_scope(engine) as s:
        s.add(
            Post(
                id=1, post_type="feed", caption_final="x", hashtags=[],
                asset_path=str(old_dir / "feed.jpg"), visual_type="headline",
                scheduled_for=old_time, published_at=old_time, status="published",
            )
        )
        s.add(
            Post(
                id=2, post_type="feed", caption_final="x", hashtags=[],
                asset_path=str(new_dir / "feed.jpg"), visual_type="headline",
                scheduled_for=new_time, published_at=new_time, status="published",
            )
        )

    summary = cleanup_old_assets(engine, posts_dir=posts_dir, age_days=30)
    assert summary.files_removed == 1
    # Old raw deleted, old final kept
    assert not (old_dir / "raw.png").exists()
    assert (old_dir / "feed.jpg").exists()
    # New raw kept
    assert (new_dir / "raw.png").exists()
```

- [ ] **Step 2: Implement `src/ig_qt/admin/cleanup.py`**

```python
"""Storage cleanup for old post assets."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.db import session_scope
from ig_qt.models import Post


@dataclass(frozen=True, slots=True)
class CleanupSummary:
    files_removed: int
    bytes_freed: int


_KEEP_FILES: frozenset[str] = frozenset({"feed.jpg", "story.jpg"})


def cleanup_old_assets(
    engine: Engine, *, posts_dir: Path, age_days: int = 30
) -> CleanupSummary:
    cutoff = datetime.now(timezone.utc) - timedelta(days=age_days)
    files_removed = 0
    bytes_freed = 0
    with session_scope(engine) as s:
        rows = list(
            s.execute(
                select(Post).where(
                    Post.status == "published",
                    Post.published_at <= cutoff,
                )
            ).scalars()
        )
        for p in rows:
            s.expunge(p)

    for post in rows:
        post_dir = posts_dir / str(post.id)
        if not post_dir.exists():
            continue
        for f in post_dir.iterdir():
            if not f.is_file():
                continue
            if f.name in _KEEP_FILES:
                continue
            try:
                size = f.stat().st_size
                f.unlink()
                files_removed += 1
                bytes_freed += size
            except OSError as exc:
                logger.warning("cleanup_skip path={} err={}", f, exc)
    logger.info(
        "cleanup_done files_removed={} bytes_freed={}", files_removed, bytes_freed
    )
    return CleanupSummary(files_removed=files_removed, bytes_freed=bytes_freed)
```

- [ ] **Step 3: Wire weekly cleanup job**

In `src/ig_qt/scheduler.py`, append to `build_jobs_spec`:

```python
        {
            "id": "weekly_cleanup",
            "trigger": CronTrigger(
                day_of_week="sun", hour=23, jitter=300, timezone=sched.timezone
            ),
        },
```

In `app.py` `run_long_running`:

```python
    async def cleanup_job() -> None:
        from ig_qt.admin.cleanup import cleanup_old_assets
        cleanup_old_assets(engine, posts_dir=cfg.paths.data_dir / "posts", age_days=30)

    handlers["weekly_cleanup"] = cleanup_job
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/admin/test_cleanup.py -v
uv run mypy --strict src/ig_qt/admin/cleanup.py
git add src/ig_qt/admin/cleanup.py src/ig_qt/scheduler.py src/ig_qt/app.py tests/admin/test_cleanup.py
git commit -m "feat(admin): add weekly asset cleanup for old published posts"
```

---

## Task 7.4: Prompt v2 (only if v1 has observed issues)

**Files (only create if needed):**
- Create: `src/ig_qt/analyst/prompts/ranker.v2.md`
- Create: `src/ig_qt/analyst/prompts/composer.v2.md`
- Modify: `src/ig_qt/analyst/runner.py` (use v2 prompts when configured)

**When to do this task:** Only if you observe ≥3 of these in the first 2 weeks of production:
- Captions reuse the same opener despite the pool variation
- LLM keeps inventing prices not in `prices_cache`
- Repetitive angle across consecutive days (despite `posted_topics` dedup)
- Disclaimer placement awkward
- Hashtag set feels generic

If issues are minor, defer this. Don't tweak prompts speculatively.

- [ ] **Step 1: Document specific symptoms first**

Create `data/logs/prompt-issues.md` (gitignored) with concrete examples:

```
### Issue 1: Generic angle on Fed news
Date: 2026-05-18
Post id: #42
Caption excerpt: "..."
Problem: ...
Hypothesis: ranker prompt doesn't penalize "obvious takes"
```

Without 3+ documented issues, do not proceed — premature prompt changes regress more than they help.

- [ ] **Step 2: Copy v1 to v2 and edit conservatively**

```bash
cp src/ig_qt/analyst/prompts/ranker.v1.md src/ig_qt/analyst/prompts/ranker.v2.md
cp src/ig_qt/analyst/prompts/composer.v1.md src/ig_qt/analyst/prompts/composer.v2.md
```

Edit only the specific bullet points addressing your documented issues.

- [ ] **Step 3: Add toggle to config**

In `config.yaml` `llm` section:

```yaml
  prompt_versions:
    ranker: v2     # was v1
    composer: v2
```

- [ ] **Step 4: Update `AnalystRunner` to read the version**

In `src/ig_qt/analyst/runner.py`, accept `ranker_prompt_name` and `composer_prompt_name` constructor args. Default to `ranker.v1` / `composer.v1`. Pass to `run_ranker` and `generate_angle`.

In `run_ranker` and `generate_angle`, accept `prompt_name: str = "ranker.v1"` (or `composer.v1`) and call `load_prompt(prompt_name)`.

- [ ] **Step 5: A/B comparison**

Run `analyze --once` with v1 prompt → save 5 outputs. Switch to v2 → run again. Compare. Roll back if v2 isn't clearly better.

- [ ] **Step 6: Commit (only if v2 wins)**

```bash
git add src/ig_qt/analyst/prompts/ranker.v2.md src/ig_qt/analyst/prompts/composer.v2.md
git add src/ig_qt/analyst/runner.py src/ig_qt/analyst/ranker.py src/ig_qt/analyst/angle_generator.py config.yaml
git commit -m "feat(analyst): promote v2 prompts based on observed regressions in v1"
```

---

## Task 7.5: Posting window timezone derivation (small refactor)

**Files:**
- Modify: `src/ig_qt/publisher/runner.py`
- Modify: `src/ig_qt/app.py`
- Modify: `tests/publisher/test_runner.py`

M5 self-review noted that `tz_offset_hours=7` is hardcoded for WIB. This task derives it from `cfg.schedule.timezone` so changing timezone in config doesn't silently break window checks.

- [ ] **Step 1: Add helper**

In `src/ig_qt/publisher/rate_limiter.py` add:

```python
import zoneinfo


def offset_hours_for_timezone(tz_name: str, *, ref: datetime | None = None) -> int:
    """Return UTC offset in hours for a given IANA tz at `ref` (default: now)."""
    tz = zoneinfo.ZoneInfo(tz_name)
    ref = ref or datetime.now(timezone.utc)
    delta = ref.astimezone(tz).utcoffset() or timedelta(0)
    return int(delta.total_seconds() // 3600)
```

- [ ] **Step 2: Use it in `app.py` `run_long_running`**

Replace hardcoded `tz_offset_hours=7` with:

```python
        tz_offset_hours=offset_hours_for_timezone(cfg.schedule.timezone),
```

- [ ] **Step 3: Test**

Add to `tests/publisher/test_rate_limiter.py`:

```python
def test_offset_hours_for_timezone() -> None:
    from ig_qt.publisher.rate_limiter import offset_hours_for_timezone
    assert offset_hours_for_timezone("Asia/Jakarta") == 7
    assert offset_hours_for_timezone("UTC") == 0
```

- [ ] **Step 4: Commit**

```bash
uv run pytest tests/publisher/test_rate_limiter.py -v
git add src/ig_qt/publisher/rate_limiter.py src/ig_qt/app.py tests/publisher/test_rate_limiter.py
git commit -m "refactor(publisher): derive tz offset from config timezone"
```

---

## Task 7.6: Documentation updates (post-launch lessons)

**Files:**
- Update: `docs/DEPLOY.md`
- Create: `docs/RUNBOOK.md`

After 2 weeks of running, capture lessons learned. Don't write speculative docs — document only what actually happened during operation.

- [ ] **Step 1: Add `docs/RUNBOOK.md` with sections:**
  - **Common log patterns** (what each `*_done`, `*_failed`, `*_skipped` log line means)
  - **Triage tree** for each Telegram alert type
  - **Restart sequences** for various failure modes
  - **Cost monitoring** (queries to check LLM token usage from `publish_log` and similar)

- [ ] **Step 2: Update `docs/DEPLOY.md`** with anything that didn't work as documented in M6 (e.g., specific OS package version pins, troubleshooting steps for first-time login on Hetzner vs Contabo, etc.).

- [ ] **Step 3: Sync vault Overview with current state**

Update `Projects/ig-qt/Overview ig-qt.md` in the Obsidian vault:
- Bump milestone status (M1–M7 progression)
- Add Pattern Library entries for any cross-project pattern that emerged
- Cross-link to Lapakflow if patterns overlap (e.g., Telegram notifier, anti-detection)

- [ ] **Step 4: Commit**

```bash
git add docs/RUNBOOK.md docs/DEPLOY.md
git commit -m "docs: add operational runbook + DEPLOY adjustments from real deploy"
```

(Vault update happens outside this repo's git history.)

---

## M7 Acceptance Criteria

Tasks in M7 are independent. Mark only those you actually executed.

- [ ] Task 7.1 done: warm-up mode tested, applied for new account if needed
- [ ] Task 7.2 done: weekly audit running, flags reviewed at least once
- [ ] Task 7.3 done: cleanup job verified to remove old `raw.png` while keeping finals
- [ ] Task 7.4 done OR explicitly deferred (no documented v1 issues yet)
- [ ] Task 7.5 done: timezone derivation in place
- [ ] Task 7.6 done: runbook captures real operational knowledge

## M7 Self-Review Notes

- **Resist speculative hardening.** Each task here costs effort. Only do those triggered by an observed problem in the first 1-2 weeks of production.
- **Warm-up mode is the highest-impact one** for accounts younger than 30 days. Skipping it is the most common cause of immediate IG flags.
- **Audit task tends to find caption issues humans miss.** Banned phrase regex is the cheapest first filter; LLM-based audit is overkill until volume justifies it.
- **Prompt v2 should be evidence-driven.** I included a hard gate (3+ documented issues) because tweaking prompts speculatively almost always regresses something subtle. Resist.
- **Cleanup job size:** `raw.png` for a 1080×1080 unoptimized headline card is ~1-3 MB. After 90 days = ~270 MB. Not urgent, but worth automating before manual `find -delete` becomes a chore.
- **Documentation update timing matters.** Writing a runbook BEFORE running the system in production produces fiction. Wait for real incidents, then document the resolution.
