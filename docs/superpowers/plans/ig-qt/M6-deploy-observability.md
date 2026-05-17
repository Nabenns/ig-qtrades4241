# M6 Deploy + Observability — Implementation Plan

> **Parent:** [`../2026-05-17-ig-forex-automation.md`](../2026-05-17-ig-forex-automation.md)
> **Prereq:** M1–M5 complete. Service runs locally via `python -m ig_qt run`.

**Goal:** Containerize the service, expose `/health` endpoint, add backup script, and document end-to-end VPS deployment. End state: VPS running `docker compose up -d` with persistent data volume; `/health` returns JSON visible to UptimeRobot; daily cron rsyncs `ig_qt.db` + `ig_session.json` offsite.

**Files created in M6:**
- `Dockerfile` (full version, replacing M1 stub if any)
- `docker-compose.yml`
- `.dockerignore` (already exists from M1, may need expansion)
- `src/ig_qt/health.py`
- `tests/test_health.py`
- `scripts/backup_session.sh`
- `scripts/restore_session.sh`
- `docs/DEPLOY.md` — VPS setup runbook
- Modify: `pyproject.toml` (add `fastapi` + `uvicorn`), `src/ig_qt/app.py`, `src/ig_qt/__main__.py`

**New dependencies:** `fastapi>=0.115`, `uvicorn[standard]>=0.30`.

---

## Task 6.1: Add web server deps + health endpoint

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ig_qt/health.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Add deps**

```toml
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
```

- [ ] **Step 2: Sync**

```bash
uv sync
```

- [ ] **Step 3: Write failing test**

`tests/test_health.py`:

```python
"""Tests for /health endpoint."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.health import build_health_app
from ig_qt.models import IGAccountState, Post, PostDraft


def _seed(engine: object, *, paused: bool = False) -> None:
    with session_scope(engine) as s:  # type: ignore[arg-type]
        s.add(
            IGAccountState(
                username="u",
                last_post_at=datetime.now(timezone.utc) - timedelta(hours=2),
                pause_until=(
                    datetime.now(timezone.utc) + timedelta(hours=1) if paused else None
                ),
                challenge_pending=paused,
            )
        )
        s.add(
            PostDraft(
                post_type="feed", source_news_ids=[], topic_tag="t", angle="a",
                key_points=["a"], caption_draft="x" * 200,
                visual_spec={"type": "headline", "headline": "x"},
                disclaimer_required=False, confidence=0.8,
                llm_provider="m", llm_model="m", prompt_version="v1",
                status="pending",
            )
        )
        s.add(
            Post(
                post_type="feed", caption_final="x", hashtags=[],
                asset_path="x", visual_type="headline",
                scheduled_for=datetime.now(timezone.utc),
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
```

- [ ] **Step 4: Implement `src/ig_qt/health.py`**

```python
"""Mini FastAPI app exposing /health for monitoring."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from sqlalchemy import Engine, func, select

from ig_qt.db import session_scope
from ig_qt.models import IGAccountState, Post, PostDraft


def build_health_app(*, engine: Engine, pause_file: Path, version: str) -> FastAPI:
    app = FastAPI(title="ig-qt health", docs_url=None, redoc_url=None, openapi_url=None)

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
            "now": datetime.now(timezone.utc).isoformat(),
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
```

- [ ] **Step 5: Run + commit**

```bash
uv run pytest tests/test_health.py -v
uv run mypy --strict src/ig_qt/health.py
git add pyproject.toml uv.lock src/ig_qt/health.py tests/test_health.py
git commit -m "feat(health): add /health endpoint with status, drafts, posts, pause info"
```

---

## Task 6.2: Wire health endpoint into long-running process

**Files:**
- Modify: `src/ig_qt/app.py`

- [ ] **Step 1: Replace `run_long_running` body to add uvicorn server**

In `src/ig_qt/app.py`, modify the `run_long_running` function. Add at top of function (replacing the `await asyncio.Event().wait()` block):

```python
    # Health endpoint server
    import uvicorn

    from ig_qt.health import build_health_app
    from ig_qt import __version__

    health_app = build_health_app(
        engine=engine,
        pause_file=cfg.paths.data_dir / "PAUSE",
        version=__version__,
    )
    server_config = uvicorn.Config(
        app=health_app,
        host="0.0.0.0",  # noqa: S104 (bind localhost-only via Docker port mapping)
        port=8080,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(server_config)

    scheduler.start()
    logger.info("scheduler_started")

    try:
        await server.serve()
    finally:
        scheduler.shutdown(wait=True)
    return 0
```

Remove the previous `await asyncio.Event().wait()` block.

- [ ] **Step 2: Smoke test locally**

```bash
uv run python -m ig_qt run &
sleep 5
curl -s http://localhost:8080/health
kill %1
```

Expected: JSON response with `status`, `pending_drafts`, etc.

- [ ] **Step 3: Commit**

```bash
git add src/ig_qt/app.py
git commit -m "feat(app): serve /health alongside scheduler in run command"
```

---

## Task 6.3: Dockerfile

**Files:**
- Create: `Dockerfile`
- Modify: `.dockerignore` (verify covers all)

- [ ] **Step 1: Verify `.dockerignore` (created in M1)** covers:

```
.git
.venv
.pytest_cache
.ruff_cache
.mypy_cache
__pycache__
*.pyc
data/
.env
.env.*
!.env.example
docs/
tests/
*.md
```

If missing entries, add them.

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# OS deps for Playwright + Pillow + matplotlib + curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    fonts-liberation fonts-dejavu-core \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libjpeg62-turbo zlib1g libpng16-16 libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv==0.4.20

WORKDIR /app

# Copy lock + manifest first for cache efficiency
COPY pyproject.toml uv.lock ./

# Install dependencies into /opt/venv (no project itself yet)
RUN uv sync --frozen --no-dev --no-install-project

# Install Chromium (headless) and OS deps via Playwright
RUN uv run playwright install --with-deps chromium

# Now copy source and install project
COPY src ./src
COPY templates ./templates
COPY assets ./assets
COPY config.yaml ./config.yaml
COPY scripts ./scripts

RUN uv sync --frozen --no-dev

# Non-root user
RUN useradd --create-home --uid 1000 igqt \
    && mkdir -p /app/data \
    && chown -R igqt:igqt /app /opt/venv

USER igqt

VOLUME ["/app/data"]
EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -fs http://localhost:8080/health || exit 1

CMD ["python", "-m", "ig_qt", "run"]
```

- [ ] **Step 3: Build locally to verify**

```bash
docker build -t ig-qt:dev .
```

Expected: build succeeds. First build takes 5-10 min (Chromium download).

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat(deploy): add production Dockerfile with Chromium and non-root user"
```

---

## Task 6.4: docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create file**

```yaml
services:
  ig-qt:
    build: .
    image: ig-qt:latest
    container_name: ig-qt
    restart: unless-stopped
    env_file: .env
    environment:
      IG_QT_DATA_DIR: /app/data
      TZ: Asia/Jakarta
    volumes:
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml:ro
    ports:
      - "127.0.0.1:8080:8080"   # localhost-only health endpoint
    healthcheck:
      test: ["CMD", "curl", "-fs", "http://localhost:8080/health"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"
```

- [ ] **Step 2: Verify compose syntax**

```bash
docker compose config
```

Expected: prints the resolved config without errors.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(deploy): add docker-compose with localhost-only health port"
```

---

## Task 6.5: Backup + restore scripts

**Files:**
- Create: `scripts/backup_session.sh`
- Create: `scripts/restore_session.sh`

- [ ] **Step 1: Create `scripts/backup_session.sh`**

```bash
#!/usr/bin/env bash
# Daily backup of critical state to offsite storage.
# Reads BACKUP_DEST from .env (e.g., user@backup.example:/backups/ig-qt or rclone:remote:bucket/ig-qt)
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found"
  exit 1
fi

# shellcheck disable=SC1091
source .env

if [[ -z "${BACKUP_DEST:-}" ]]; then
  echo "ERROR: BACKUP_DEST not set in .env"
  exit 1
fi

DATE=$(date -u +"%Y%m%dT%H%M%SZ")
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

# Snapshot SQLite to avoid copying mid-write file
docker compose exec -T ig-qt sqlite3 /app/data/ig_qt.db ".backup '/app/data/ig_qt.snapshot.db'"
cp data/ig_qt.snapshot.db "$TMP_DIR/ig_qt-${DATE}.db"
rm data/ig_qt.snapshot.db

# Copy session files
[[ -f data/ig_session.json ]] && cp data/ig_session.json "$TMP_DIR/ig_session-${DATE}.json"

# Push to destination
case "$BACKUP_DEST" in
  rclone:*)
    REMOTE="${BACKUP_DEST#rclone:}"
    rclone copy "$TMP_DIR/" "$REMOTE/" --transfers=4 --quiet
    ;;
  *:*)
    rsync -avz --quiet "$TMP_DIR/" "$BACKUP_DEST/"
    ;;
  *)
    # Local path backup
    mkdir -p "$BACKUP_DEST"
    cp "$TMP_DIR"/* "$BACKUP_DEST/"
    ;;
esac

echo "Backup complete: $DATE"
```

- [ ] **Step 2: Create `scripts/restore_session.sh`**

```bash
#!/usr/bin/env bash
# Restore latest session.json + ig_qt.db from backup destination.
# Usage: ./scripts/restore_session.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source .env

if [[ -z "${BACKUP_DEST:-}" ]]; then
  echo "ERROR: BACKUP_DEST not set"
  exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

case "$BACKUP_DEST" in
  rclone:*)
    REMOTE="${BACKUP_DEST#rclone:}"
    rclone copy "$REMOTE/" "$TMP_DIR/" --include "ig_*"
    ;;
  *:*)
    rsync -avz "$BACKUP_DEST/" "$TMP_DIR/"
    ;;
  *)
    cp -r "$BACKUP_DEST"/* "$TMP_DIR/"
    ;;
esac

# Find latest by filename (sorted lexicographically)
LATEST_DB=$(ls -1 "$TMP_DIR"/ig_qt-*.db 2>/dev/null | sort | tail -1)
LATEST_SESSION=$(ls -1 "$TMP_DIR"/ig_session-*.json 2>/dev/null | sort | tail -1)

if [[ -z "$LATEST_DB" ]]; then
  echo "ERROR: no ig_qt-*.db found in backup"
  exit 1
fi

echo "Restoring DB from $LATEST_DB"
echo "WARNING: this will overwrite data/ig_qt.db. Stop the service first."
read -r -p "Continue? [y/N]: " CONFIRM
[[ "$CONFIRM" == "y" ]] || exit 0

docker compose down || true
mkdir -p data
cp "$LATEST_DB" data/ig_qt.db
[[ -n "$LATEST_SESSION" ]] && cp "$LATEST_SESSION" data/ig_session.json

echo "Restored. Start service with: docker compose up -d"
```

- [ ] **Step 3: Make executable**

```bash
chmod +x scripts/backup_session.sh scripts/restore_session.sh
```

- [ ] **Step 4: Add `BACKUP_DEST` to `.env.example`**

Append:

```env
# Offsite backup target. Examples:
#   user@host:/backups/ig-qt           (rsync over SSH)
#   rclone:b2:my-bucket/ig-qt          (rclone remote)
#   /mnt/backups/ig-qt                 (local mount)
BACKUP_DEST=
```

- [ ] **Step 5: Commit**

```bash
git add scripts/backup_session.sh scripts/restore_session.sh .env.example
git commit -m "feat(deploy): add backup and restore scripts for DB and IG session"
```

---

## Task 6.6: VPS deployment runbook

**Files:**
- Create: `docs/DEPLOY.md`

- [ ] **Step 1: Create `docs/DEPLOY.md`**

````markdown
# Deployment Runbook (VPS)

## Target

- Linux VPS with Docker + docker compose plugin (Ubuntu 22.04+ or Debian 12+).
- Minimum: 2 vCPU, 2 GB RAM, 20 GB disk.
- Recommended: 2 vCPU, 4 GB RAM (Hetzner CX22 ~€4/mo or Contabo VPS S ~$6/mo).

## One-time setup

1. **Provision the VPS** and SSH in.

2. **Install Docker + Compose:**
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker "$USER"
   # Logout + login for group to apply
   ```

3. **Clone repo:**
   ```bash
   git clone <your-repo-url> /opt/ig-qt
   cd /opt/ig-qt
   ```

4. **Configure secrets:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Fill in:
   - `LLM_BASE_URL`, `LLM_API_KEY`
   - `IG_USERNAME`, `IG_PASSWORD`
   - `NEWSAPI_KEY`, `GNEWS_KEY`, `TWELVEDATA_KEY`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   - `BACKUP_DEST`

5. **Build the image:**
   ```bash
   docker compose build
   ```

6. **First-time IG login (interactive):**
   ```bash
   docker compose run --rm ig-qt python scripts/ig_login_first_time.py
   ```
   Follow prompts. If Instagram requests a verification code (email/SMS), enter it. On success, `data/ig_session.json` is created and backed up to `data/backups/`.

7. **Seed evergreen content pool:**
   ```bash
   docker compose run --rm ig-qt python scripts/generate_evergreen.py
   ```
   Generates ~10 evergreen drafts for dry-day fallback.

8. **Start the service:**
   ```bash
   docker compose up -d
   docker compose logs -f
   ```
   Wait until you see `scheduler_started`. Stop following logs with Ctrl+C (the service keeps running).

9. **Verify health:**
   ```bash
   curl -s http://localhost:8080/health | jq
   ```
   Expected: JSON with `status: "ok"`.

## Daily backup cron

Edit crontab:

```bash
crontab -e
```

Append:

```cron
0 4 * * * cd /opt/ig-qt && ./scripts/backup_session.sh >> data/logs/backup.log 2>&1
```

Backup runs at 04:00 UTC daily.

## Operational commands

| Task | Command |
|---|---|
| View logs | `docker compose logs -f --tail 200` |
| Pause publisher | `touch /opt/ig-qt/data/PAUSE` |
| Resume publisher | `rm /opt/ig-qt/data/PAUSE` |
| Restart | `docker compose restart` |
| Update | `git pull && docker compose build && docker compose up -d` |
| Inspect DB | `docker compose exec ig-qt sqlite3 /app/data/ig_qt.db` |
| Check health | `curl -s http://localhost:8080/health \| jq` |
| Manual collect | `docker compose exec ig-qt python -m ig_qt collect` |
| Manual analyze | `docker compose exec ig-qt python -m ig_qt analyze` |
| Manual compose | `docker compose exec ig-qt python -m ig_qt compose` |

## Monitoring

1. **UptimeRobot (free):**
   - Add HTTP(s) monitor.
   - URL: `http://<vps-ip>:8080/health` (or use `ssh -L 8080:localhost:8080` if you keep the port localhost-only — recommended).
   - Alternative: run a tiny reverse proxy on port 80 with HTTP basic auth pointing to localhost:8080 + UptimeRobot keyword check for `"status": "ok"`.

2. **Telegram alerts:** automatic from publisher on Challenge / Feedback / failed publish.

## Recovery scenarios

### Session expired
```bash
docker compose down
docker compose run --rm ig-qt python scripts/ig_login_first_time.py
docker compose up -d
```

### Account challenge (Telegram alert received)
1. Open Instagram app on your phone, log in, complete the challenge manually.
2. Wait 24h to be safe.
3. On VPS:
   ```bash
   docker compose exec ig-qt sqlite3 /app/data/ig_qt.db \
     "UPDATE ig_account_state SET pause_until = NULL, challenge_pending = 0 WHERE id = 1"
   docker compose restart
   ```

### VPS lost / migration
1. Provision new VPS, install Docker.
2. Clone repo, copy `.env` from secure storage.
3. `docker compose build`.
4. Restore from backup:
   ```bash
   ./scripts/restore_session.sh
   ```
5. Start: `docker compose up -d`.

## Security

- `.env` is gitignored. Keep a copy in a password manager or sealed vault.
- `data/ig_session.json` grants posting rights to your IG account. Treat as a credential — back up to encrypted offsite.
- Do not expose port 8080 to the public internet without auth. The compose binds to `127.0.0.1` by default.
- Pin the Docker image tag in production (`image: ig-qt:vX.Y.Z`) and bump deliberately.
````

- [ ] **Step 2: Commit**

```bash
git add docs/DEPLOY.md
git commit -m "docs(deploy): add VPS deployment runbook"
```

---

## Task 6.7: End-to-end smoke test on VPS

**Goal:** verify full M1–M6 stack on the actual target host before declaring M6 done. This is operational verification, not a code task.

- [ ] **Step 1: Deploy following `docs/DEPLOY.md` steps 1–7**

- [ ] **Step 2: Service health**

```bash
curl -s http://localhost:8080/health | jq
```

Expected: `status` is `ok`.

- [ ] **Step 3: Manual one-shot pipeline**

```bash
docker compose exec ig-qt python -m ig_qt collect
docker compose exec ig-qt python -m ig_qt analyze
docker compose exec ig-qt python -m ig_qt compose
```

Expected:
- `data/ig_qt.db` has rows in `raw_news`, `events`, `post_drafts`, `posts`.
- `data/posts/<id>/feed.jpg` exists, 1080×1080, < 8 MB.

- [ ] **Step 4: Test pause file**

```bash
touch data/PAUSE
docker compose logs --tail 20
# next publisher_loop tick should log "publisher_skipped reason=pause_file"
rm data/PAUSE
```

- [ ] **Step 5: Test backup**

```bash
./scripts/backup_session.sh
```

Expected: prints `Backup complete: <date>`. Verify destination has new files.

- [ ] **Step 6: Wait one full cron cycle (or trigger via temporary cron)** to confirm scheduled jobs fire (see logs).

- [ ] **Step 7: Optionally**: subscribe to UptimeRobot / Better Stack and confirm health alerts work.

---

## M6 Acceptance Criteria

- [ ] All `tests/test_health.py` green
- [ ] `mypy --strict src/ig_qt/health.py` clean
- [ ] `docker build -t ig-qt:dev .` succeeds locally
- [ ] `docker compose config` validates without errors
- [ ] `docker compose up -d` brings up service; `curl http://localhost:8080/health` returns 200 + JSON
- [ ] `docker compose down && docker compose up -d` preserves DB and session (volume persistence verified)
- [ ] First-time login script run inside container succeeds; `data/ig_session.json` written
- [ ] Backup script runs and pushes to `BACKUP_DEST`
- [ ] Restore script (dry tested) restores from backup
- [ ] `docs/DEPLOY.md` reflects the actual deployment steps that worked
- [ ] All M6 tasks committed individually

## M6 Self-Review Notes

- **Why bind health endpoint to 0.0.0.0 inside container but `127.0.0.1:8080` on host:** Docker port mapping `127.0.0.1:8080:8080` means only localhost on the host can reach it. SSH tunnel (`ssh -L 8080:localhost:8080`) lets you check from your laptop without exposing publicly. Avoids needing TLS + auth in v1.
- **Non-root user inside container:** UID 1000 matches typical Ubuntu user, so volume mounts written by container are owned by your VPS user — easier `tar`/`rsync` backup.
- **Healthcheck inside Dockerfile vs compose:** both exist. Compose-level used for restart policy; Dockerfile-level used for `docker ps` status. Both point to the same endpoint.
- **`uv run` not used in CMD:** the `PATH=/opt/venv/bin:$PATH` makes `python` directly resolve. Saves ~200 ms startup.
- **Playwright `--with-deps chromium`:** installs Chromium browser binary + missing OS deps in one step. Slimmer than installing every Playwright browser.
- **SQLite backup uses `.backup` command:** safe even if writes are happening (proper online backup). Plain `cp` on a SQLite file under WAL mode can produce a corrupt backup.
- **`BACKUP_DEST` accepts three forms:** rsync over SSH, rclone remote, local path. Pick what fits your setup. Backblaze B2 via rclone is cheapest cloud option (~$1/mo for tens of GB).
- **No log shipping to external service in v1:** Loguru writes to `data/logs/`, Docker writes JSON-file driver logs. Sufficient until usage justifies adding Loki/Grafana — defer to M7 hardening.
- **`docker compose build` not in cron:** updates are explicit. Auto-rebuild on git pull is dangerous (unreviewed prompt changes posting to public IG).
