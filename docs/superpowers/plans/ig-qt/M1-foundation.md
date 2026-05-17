# M1 Foundation — Implementation Plan

> **Parent:** [`../2026-05-17-ig-forex-automation.md`](../2026-05-17-ig-forex-automation.md)
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Bootstrap project skeleton: Python 3.12 + uv project, repo layout, config loader, SQLite schema + SQLAlchemy models, LLM provider factory (Protocol + adapters), Telegram notifier, basic Loguru logging. End state: `python -m ig_qt --check` validates env + DB and exits cleanly.

**Files created in M1:**
- `pyproject.toml`, `uv.lock`, `.env.example`, `.python-version`
- `Dockerfile` (stub, expanded in M6), `.dockerignore`
- `config.yaml`
- `src/ig_qt/__init__.py`, `__main__.py`, `app.py`
- `src/ig_qt/config.py`
- `src/ig_qt/db.py`, `models.py`
- `src/ig_qt/logging_setup.py`
- `src/ig_qt/llm/base.py`, `factory.py`, `router_9.py`, `openai_provider.py`, `anthropic_provider.py`, `gemini_provider.py`
- `src/ig_qt/notifier.py`
- `tests/conftest.py`, `tests/test_config.py`, `tests/test_db.py`, `tests/test_llm_factory.py`, `tests/test_notifier.py`

---

## Task 1.1: Initialize uv project + pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Initialize uv**

```bash
uv init --python 3.12 --no-readme --no-pin-python
```

Expected: creates `pyproject.toml`, `.python-version`. Modify both as below.

- [ ] **Step 2: Replace `pyproject.toml`**

```toml
[project]
name = "ig-qt"
version = "0.1.0"
description = "Automated Instagram content system for forex/finance accounts"
requires-python = ">=3.12,<3.13"
dependencies = [
    "pydantic>=2.7",
    "pydantic-settings>=2.4",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "loguru>=0.7",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "tenacity>=9.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "mypy>=1.11",
    "ruff>=0.6",
    "types-pyyaml>=6.0",
]

[tool.uv]
package = true

[tool.hatch.build.targets.wheel]
packages = ["src/ig_qt"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.mypy]
strict = true
python_version = "3.12"
plugins = ["pydantic.mypy"]
exclude = ["build/", "dist/"]

[[tool.mypy.overrides]]
module = ["instagrapi.*", "mplfinance.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC", "S", "RET", "SIM"]
ignore = ["S101"]  # allow asserts in tests

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S105", "S106"]
```

- [ ] **Step 3: Create `.env.example`**

```env
# LLM
LLM_BASE_URL=https://9router.example.com/v1
LLM_API_KEY=changeme

# IG
IG_USERNAME=changeme
IG_PASSWORD=changeme

# Data sources
NEWSAPI_KEY=changeme
GNEWS_KEY=changeme
TWELVEDATA_KEY=changeme

# Notifier
TELEGRAM_BOT_TOKEN=changeme
TELEGRAM_CHAT_ID=changeme

# Runtime
APP_ENV=dev
```

- [ ] **Step 4: Create minimal `README.md`**

```markdown
# ig-qt

Automated Instagram content system for forex/finance.

See `docs/superpowers/specs/2026-05-17-ig-forex-automation-design.md` for design.
See `docs/superpowers/plans/2026-05-17-ig-forex-automation.md` for implementation plan.

## Quickstart (dev)

```bash
uv sync
cp .env.example .env  # fill secrets
uv run python -m ig_qt --check
```
```

- [ ] **Step 5: Run `uv sync` to install**

```bash
uv sync
```

Expected: creates `.venv/` and `uv.lock`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .python-version .env.example README.md
git commit -m "chore(scaffold): initialize uv project and dependencies"
```

---

## Task 1.2: Repo layout + .gitignore + .dockerignore

**Files:**
- Modify: `.gitignore`
- Create: `.dockerignore`
- Create: `src/ig_qt/__init__.py`
- Create: `src/ig_qt/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `data/.gitkeep`

- [ ] **Step 1: Replace `.gitignore` with full version**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
*.egg-info/
build/
dist/

# Env & secrets
.env
.env.*
!.env.example
*.session
*.session.json

# Data (runtime)
data/*
!data/.gitkeep

# Logs
*.log

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 2: Create `.dockerignore`**

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

- [ ] **Step 3: Create `src/ig_qt/__init__.py`**

```python
"""ig-qt: automated Instagram content system for forex/finance."""
from __future__ import annotations

__version__ = "0.1.0"
```

- [ ] **Step 4: Create `src/ig_qt/__main__.py` (placeholder)**

```python
"""Entry point: `python -m ig_qt`."""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="ig_qt")
    parser.add_argument("--check", action="store_true", help="Validate env/DB and exit")
    args = parser.parse_args()
    if args.check:
        # Wired up in Task 1.8
        print("check: not implemented yet")
        return 0
    print("ig_qt: not implemented yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Create `tests/__init__.py` (empty) and `tests/conftest.py`**

`tests/__init__.py`: empty file.

`tests/conftest.py`:

```python
"""Shared pytest fixtures."""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Run each test in a clean env with tmp data dir."""
    for k in list(os.environ.keys()):
        if k.startswith(("LLM_", "IG_", "NEWSAPI_", "GNEWS_", "TWELVEDATA_", "TELEGRAM_")):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("IG_QT_DATA_DIR", str(tmp_path))
    yield
```

- [ ] **Step 6: Create `data/.gitkeep`**

Empty file.

- [ ] **Step 7: Verify import works**

```bash
uv run python -c "import ig_qt; print(ig_qt.__version__)"
```

Expected: `0.1.0`

- [ ] **Step 8: Verify `__main__` runs**

```bash
uv run python -m ig_qt --check
```

Expected: `check: not implemented yet` and exit 0.

- [ ] **Step 9: Commit**

```bash
git add .gitignore .dockerignore src/ tests/ data/.gitkeep
git commit -m "chore(scaffold): add repo layout and entrypoint stub"
```

---

## Task 1.3: Logging setup (Loguru)

**Files:**
- Create: `src/ig_qt/logging_setup.py`
- Create: `tests/test_logging_setup.py`

- [ ] **Step 1: Write failing test**

`tests/test_logging_setup.py`:

```python
"""Tests for logging setup."""
from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from ig_qt.logging_setup import configure_logging


def test_configure_logging_writes_json_to_file(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    configure_logging(log_dir=tmp_path, level="INFO", json_logs=True)
    logger.info("hello", extra_key="extra_value")
    # flush sinks
    logger.complete()
    content = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert content, "log file should not be empty"
    record = json.loads(content[-1])
    assert record["record"]["message"] == "hello"


def test_configure_logging_redacts_secrets(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    configure_logging(log_dir=tmp_path, level="INFO", json_logs=False)
    logger.info("api_key=sk-secret123 should be redacted")
    logger.complete()
    text = log_file.read_text(encoding="utf-8")
    assert "sk-secret123" not in text
    assert "api_key=" in text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_logging_setup.py -v
```

Expected: FAIL with `ModuleNotFoundError: ig_qt.logging_setup`.

- [ ] **Step 3: Implement `src/ig_qt/logging_setup.py`**

```python
"""Centralized Loguru configuration."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from loguru import logger

# Patterns that look like secrets in log lines.
_SECRET_PATTERNS = [
    re.compile(r"(api_key=)([A-Za-z0-9_\-\.]+)"),
    re.compile(r"(password=)(\S+)"),
    re.compile(r"(token=)([A-Za-z0-9_\-\.]+)"),
    re.compile(r"(Bearer\s+)([A-Za-z0-9_\-\.]+)", re.IGNORECASE),
]


def _redact(record: dict) -> None:
    msg = record["message"]
    for pat in _SECRET_PATTERNS:
        msg = pat.sub(r"\1[REDACTED]", msg)
    record["message"] = msg


def configure_logging(
    *,
    log_dir: Path,
    level: str = "INFO",
    json_logs: bool = True,
) -> None:
    """Configure Loguru sinks: stderr (human) + file (JSON or text)."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()

    def patcher(record: dict) -> None:
        _redact(record)

    logger.configure(patcher=patcher)

    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "<level>{level: <8}</level> "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
            "- <level>{message}</level>"
        ),
        backtrace=False,
        diagnose=False,
    )

    logger.add(
        log_dir / "app.log",
        level=level,
        rotation="100 MB",
        retention="30 days",
        serialize=json_logs,
        backtrace=False,
        diagnose=False,
        enqueue=True,
    )

    logger.add(
        log_dir / "errors.log",
        level="ERROR",
        rotation="50 MB",
        retention="90 days",
        serialize=json_logs,
        backtrace=True,
        diagnose=False,
        enqueue=True,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_logging_setup.py -v
```

Expected: PASS.

- [ ] **Step 5: Run mypy**

```bash
uv run mypy --strict src/ig_qt/logging_setup.py
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add src/ig_qt/logging_setup.py tests/test_logging_setup.py
git commit -m "feat(logging): add Loguru setup with JSON sinks and secret redaction"
```

---

## Task 1.4: Pydantic Settings config loader

**Files:**
- Create: `config.yaml`
- Create: `src/ig_qt/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create `config.yaml` (committed defaults)**

```yaml
# Non-secret config. Secrets live in .env.
brand:
  primary: "#0a84ff"
  accent: "#ffb020"
  font: "Inter"
  handle: "@your_handle_here"
  logo_path: "assets/logo.png"

llm:
  provider: router_9    # router_9 | openai | anthropic | gemini
  base_url_env: LLM_BASE_URL
  api_key_env: LLM_API_KEY
  models:
    ranker: gemini-2.0-flash
    composer: claude-sonnet-4
  request_timeout_seconds: 30
  max_retries: 2

schedule:
  timezone: Asia/Jakarta
  feed_post_hour: 11
  feed_post_jitter_minutes: 15
  story_event_hour: 12
  story_recap_hour: 21
  skip_day_probability: 0.14
  posting_window_start_hour: 6
  posting_window_end_hour: 23

ig:
  username_env: IG_USERNAME
  password_env: IG_PASSWORD
  max_feed_per_day: 2
  max_feed_per_week: 10
  max_story_per_day: 5
  max_login_per_day: 1
  delay_range_seconds: [2, 5]

collector:
  news_api_enabled: true
  news_api_key_env: NEWSAPI_KEY
  gnews_enabled: true
  gnews_key_env: GNEWS_KEY
  twelve_data_enabled: true
  twelve_data_key_env: TWELVEDATA_KEY
  forex_factory_enabled: true
  symbols:
    - EUR/USD
    - GBP/USD
    - USD/JPY
    - XAU/USD
    - DXY
    - BTC/USD

notifier:
  telegram_enabled: true
  telegram_bot_token_env: TELEGRAM_BOT_TOKEN
  telegram_chat_id_env: TELEGRAM_CHAT_ID

paths:
  data_dir_env: IG_QT_DATA_DIR
  data_dir_default: data
```

- [ ] **Step 2: Write failing test**

`tests/test_config.py`:

```python
"""Tests for config loader."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ig_qt.config import AppConfig, load_config


@pytest.fixture
def yaml_path(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "brand": {
                    "primary": "#000",
                    "accent": "#fff",
                    "font": "Inter",
                    "handle": "@x",
                    "logo_path": "assets/logo.png",
                },
                "llm": {
                    "provider": "router_9",
                    "base_url_env": "LLM_BASE_URL",
                    "api_key_env": "LLM_API_KEY",
                    "models": {"ranker": "r", "composer": "c"},
                    "request_timeout_seconds": 30,
                    "max_retries": 2,
                },
                "schedule": {
                    "timezone": "Asia/Jakarta",
                    "feed_post_hour": 11,
                    "feed_post_jitter_minutes": 15,
                    "story_event_hour": 12,
                    "story_recap_hour": 21,
                    "skip_day_probability": 0.14,
                    "posting_window_start_hour": 6,
                    "posting_window_end_hour": 23,
                },
                "ig": {
                    "username_env": "IG_USERNAME",
                    "password_env": "IG_PASSWORD",
                    "max_feed_per_day": 2,
                    "max_feed_per_week": 10,
                    "max_story_per_day": 5,
                    "max_login_per_day": 1,
                    "delay_range_seconds": [2, 5],
                },
                "collector": {
                    "news_api_enabled": True,
                    "news_api_key_env": "NEWSAPI_KEY",
                    "gnews_enabled": True,
                    "gnews_key_env": "GNEWS_KEY",
                    "twelve_data_enabled": True,
                    "twelve_data_key_env": "TWELVEDATA_KEY",
                    "forex_factory_enabled": True,
                    "symbols": ["EUR/USD"],
                },
                "notifier": {
                    "telegram_enabled": True,
                    "telegram_bot_token_env": "TELEGRAM_BOT_TOKEN",
                    "telegram_chat_id_env": "TELEGRAM_CHAT_ID",
                },
                "paths": {
                    "data_dir_env": "IG_QT_DATA_DIR",
                    "data_dir_default": "data",
                },
            }
        ),
        encoding="utf-8",
    )
    return p


def test_load_config_returns_app_config(yaml_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("IG_USERNAME", "u")
    monkeypatch.setenv("IG_PASSWORD", "p")
    monkeypatch.setenv("NEWSAPI_KEY", "n")
    monkeypatch.setenv("GNEWS_KEY", "g")
    monkeypatch.setenv("TWELVEDATA_KEY", "t")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "b")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    cfg = load_config(yaml_path)
    assert isinstance(cfg, AppConfig)
    assert cfg.llm.provider == "router_9"
    assert cfg.llm.api_key.get_secret_value() == "k"
    assert cfg.ig.password.get_secret_value() == "p"
    assert cfg.schedule.feed_post_hour == 11
    assert cfg.collector.symbols == ["EUR/USD"]


def test_load_config_missing_required_secret_fails(
    yaml_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Don't set LLM_API_KEY → should fail validation
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("IG_USERNAME", "u")
    monkeypatch.setenv("IG_PASSWORD", "p")
    monkeypatch.setenv("NEWSAPI_KEY", "n")
    monkeypatch.setenv("GNEWS_KEY", "g")
    monkeypatch.setenv("TWELVEDATA_KEY", "t")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "b")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        load_config(yaml_path)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `src/ig_qt/config.py`**

```python
"""Application configuration loaded from config.yaml + environment."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class BrandConfig(BaseModel):
    primary: str
    accent: str
    font: str
    handle: str
    logo_path: str


class LLMConfig(BaseModel):
    provider: Literal["router_9", "openai", "anthropic", "gemini"]
    base_url: str
    api_key: SecretStr
    ranker_model: str
    composer_model: str
    request_timeout_seconds: int = 30
    max_retries: int = 2


class ScheduleConfig(BaseModel):
    timezone: str
    feed_post_hour: int
    feed_post_jitter_minutes: int
    story_event_hour: int
    story_recap_hour: int
    skip_day_probability: float = Field(ge=0.0, le=1.0)
    posting_window_start_hour: int = Field(ge=0, le=23)
    posting_window_end_hour: int = Field(ge=0, le=23)


class IGConfig(BaseModel):
    username: str
    password: SecretStr
    max_feed_per_day: int
    max_feed_per_week: int
    max_story_per_day: int
    max_login_per_day: int
    delay_range_seconds: tuple[float, float]

    @field_validator("delay_range_seconds", mode="before")
    @classmethod
    def _coerce_delay(cls, v: object) -> tuple[float, float]:
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return (float(v[0]), float(v[1]))
        raise ValueError("delay_range_seconds must be 2-element list")


class CollectorConfig(BaseModel):
    news_api_enabled: bool
    news_api_key: SecretStr | None
    gnews_enabled: bool
    gnews_key: SecretStr | None
    twelve_data_enabled: bool
    twelve_data_key: SecretStr | None
    forex_factory_enabled: bool
    symbols: list[str]


class NotifierConfig(BaseModel):
    telegram_enabled: bool
    telegram_bot_token: SecretStr | None
    telegram_chat_id: str | None


class PathsConfig(BaseModel):
    data_dir: Path


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    brand: BrandConfig
    llm: LLMConfig
    schedule: ScheduleConfig
    ig: IGConfig
    collector: CollectorConfig
    notifier: NotifierConfig
    paths: PathsConfig


def _require_env(var: str) -> str:
    val = os.environ.get(var)
    if not val:
        raise ValueError(f"required env var missing: {var}")
    return val


def _optional_env(var: str) -> str | None:
    return os.environ.get(var) or None


def load_config(yaml_path: Path) -> AppConfig:
    """Load config.yaml and resolve env-backed secrets."""
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

    llm_raw = raw["llm"]
    llm = LLMConfig(
        provider=llm_raw["provider"],
        base_url=_require_env(llm_raw["base_url_env"]),
        api_key=SecretStr(_require_env(llm_raw["api_key_env"])),
        ranker_model=llm_raw["models"]["ranker"],
        composer_model=llm_raw["models"]["composer"],
        request_timeout_seconds=llm_raw.get("request_timeout_seconds", 30),
        max_retries=llm_raw.get("max_retries", 2),
    )

    ig_raw = raw["ig"]
    ig = IGConfig(
        username=_require_env(ig_raw["username_env"]),
        password=SecretStr(_require_env(ig_raw["password_env"])),
        max_feed_per_day=ig_raw["max_feed_per_day"],
        max_feed_per_week=ig_raw["max_feed_per_week"],
        max_story_per_day=ig_raw["max_story_per_day"],
        max_login_per_day=ig_raw["max_login_per_day"],
        delay_range_seconds=tuple(ig_raw["delay_range_seconds"]),
    )

    coll_raw = raw["collector"]

    def _coll_secret(key: str, enabled_key: str) -> SecretStr | None:
        if not coll_raw.get(enabled_key):
            return None
        env_var = coll_raw.get(key)
        if not env_var:
            return None
        val = _optional_env(env_var)
        if val is None:
            raise ValueError(f"required env var missing: {env_var}")
        return SecretStr(val)

    collector = CollectorConfig(
        news_api_enabled=coll_raw["news_api_enabled"],
        news_api_key=_coll_secret("news_api_key_env", "news_api_enabled"),
        gnews_enabled=coll_raw["gnews_enabled"],
        gnews_key=_coll_secret("gnews_key_env", "gnews_enabled"),
        twelve_data_enabled=coll_raw["twelve_data_enabled"],
        twelve_data_key=_coll_secret("twelve_data_key_env", "twelve_data_enabled"),
        forex_factory_enabled=coll_raw["forex_factory_enabled"],
        symbols=list(coll_raw["symbols"]),
    )

    notif_raw = raw["notifier"]
    if notif_raw["telegram_enabled"]:
        notifier = NotifierConfig(
            telegram_enabled=True,
            telegram_bot_token=SecretStr(_require_env(notif_raw["telegram_bot_token_env"])),
            telegram_chat_id=_require_env(notif_raw["telegram_chat_id_env"]),
        )
    else:
        notifier = NotifierConfig(
            telegram_enabled=False, telegram_bot_token=None, telegram_chat_id=None
        )

    paths_raw = raw["paths"]
    data_dir = Path(
        os.environ.get(paths_raw["data_dir_env"], paths_raw["data_dir_default"])
    ).resolve()

    return AppConfig(
        brand=BrandConfig(**raw["brand"]),
        llm=llm,
        schedule=ScheduleConfig(**raw["schedule"]),
        ig=ig,
        collector=collector,
        notifier=notifier,
        paths=PathsConfig(data_dir=data_dir),
    )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 6: Run mypy**

```bash
uv run mypy --strict src/ig_qt/config.py
```

Expected: `Success: no issues found`.

- [ ] **Step 7: Commit**

```bash
git add config.yaml src/ig_qt/config.py tests/test_config.py
git commit -m "feat(config): add Pydantic Settings loader with env-backed secrets"
```

---

## Task 1.5: SQLAlchemy DB layer + initial models

**Files:**
- Create: `src/ig_qt/db.py`
- Create: `src/ig_qt/models.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing test**

`tests/test_db.py`:

```python
"""Tests for DB layer."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import IGAccountState, RawNews


def test_init_schema_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = build_engine(db_path)
    init_schema(engine)
    with session_scope(engine) as s:
        # Insert + read sanity check
        s.add(
            RawNews(
                source="test",
                external_id="1",
                title="hello",
                url="https://x",
                dedup_key="abc",
            )
        )
        s.flush()
        rows = s.execute(select(RawNews)).scalars().all()
        assert len(rows) == 1
        assert rows[0].title == "hello"


def test_session_scope_rolls_back_on_error(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = build_engine(db_path)
    init_schema(engine)
    try:
        with session_scope(engine) as s:
            s.add(IGAccountState(username="u"))
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    with session_scope(engine) as s:
        rows = s.execute(select(IGAccountState)).scalars().all()
        assert rows == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_db.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `src/ig_qt/models.py`**

```python
"""SQLAlchemy ORM models."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON, Mapping[str, Any]: JSON}


class RawNews(Base):
    __tablename__ = "raw_news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str | None] = mapped_column(String(256))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[Any] | None] = mapped_column(JSON)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    dedup_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    country: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(Text)
    impact: Mapped[str] = mapped_column(String(16))  # low | medium | high
    forecast: Mapped[str | None] = mapped_column(String(64))
    previous: Mapped[str | None] = mapped_column(String(64))
    actual: Mapped[str | None] = mapped_column(String(64))
    dedup_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PriceCache(Base):
    __tablename__ = "prices_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    ohlc_json: Mapped[list[Any]] = mapped_column(JSON)


class PostDraft(Base):
    __tablename__ = "post_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_type: Mapped[str] = mapped_column(String(16))  # feed | story
    source_news_ids: Mapped[list[Any] | None] = mapped_column(JSON)
    topic_tag: Mapped[str] = mapped_column(String(128), index=True)
    angle: Mapped[str] = mapped_column(Text)
    key_points: Mapped[list[Any]] = mapped_column(JSON)
    caption_draft: Mapped[str] = mapped_column(Text)
    visual_spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    disclaimer_required: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float)
    llm_provider: Mapped[str] = mapped_column(String(32))
    llm_model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    posts: Mapped[list["Post"]] = relationship(back_populates="draft")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("post_drafts.id"))
    post_type: Mapped[str] = mapped_column(String(16))
    caption_final: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[list[Any]] = mapped_column(JSON)
    asset_path: Mapped[str] = mapped_column(Text)
    visual_type: Mapped[str] = mapped_column(String(32))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ready", index=True)
    ig_media_id: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_log: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    draft: Mapped[PostDraft | None] = relationship(back_populates="posts")


class PublishLog(Base):
    __tablename__ = "publish_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    ig_media_id: Mapped[str | None] = mapped_column(String(64))
    ig_account_pk: Mapped[str | None] = mapped_column(String(64))
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16))  # success | failed | challenge
    error_type: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    took_ms: Mapped[int | None] = mapped_column(Integer)


class IGAccountState(Base):
    __tablename__ = "ig_account_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    challenge_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    pause_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daily_post_count: Mapped[int] = mapped_column(Integer, default=0)
    weekly_post_count: Mapped[int] = mapped_column(Integer, default=0)


class PostedTopic(Base):
    __tablename__ = "posted_topics"

    topic_tag: Mapped[str] = mapped_column(String(128), primary_key=True)
    last_posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
```

- [ ] **Step 4: Implement `src/ig_qt/db.py`**

```python
"""SQLite engine + session helpers."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from ig_qt.models import Base


def build_engine(db_path: Path) -> Engine:
    """Create SQLite engine with WAL mode + foreign keys ON."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _conn_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def init_schema(engine: Engine) -> None:
    """Create all tables (idempotent)."""
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Session context: commit on success, rollback on exception."""
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_db.py -v
```

Expected: PASS.

- [ ] **Step 6: Run mypy**

```bash
uv run mypy --strict src/ig_qt/db.py src/ig_qt/models.py
```

Expected: `Success: no issues found`.

- [ ] **Step 7: Commit**

```bash
git add src/ig_qt/db.py src/ig_qt/models.py tests/test_db.py
git commit -m "feat(db): add SQLAlchemy models and SQLite engine helpers"
```

---

## Task 1.6: LLM provider Protocol + factory + adapters

**Files:**
- Create: `src/ig_qt/llm/__init__.py`
- Create: `src/ig_qt/llm/base.py`
- Create: `src/ig_qt/llm/factory.py`
- Create: `src/ig_qt/llm/router_9.py`
- Create: `src/ig_qt/llm/openai_provider.py`
- Create: `src/ig_qt/llm/anthropic_provider.py`
- Create: `src/ig_qt/llm/gemini_provider.py`
- Create: `tests/test_llm_factory.py`

- [ ] **Step 1: Write failing test**

`tests/test_llm_factory.py`:

```python
"""Tests for LLM factory."""
from __future__ import annotations

import pytest
from pydantic import SecretStr

from ig_qt.config import LLMConfig
from ig_qt.llm.base import LLMProvider
from ig_qt.llm.factory import build_llm_provider


@pytest.mark.parametrize("provider_name", ["router_9", "openai", "anthropic", "gemini"])
def test_factory_returns_provider_for_each_name(provider_name: str) -> None:
    cfg = LLMConfig(
        provider=provider_name,  # type: ignore[arg-type]
        base_url="https://x",
        api_key=SecretStr("k"),
        ranker_model="r",
        composer_model="c",
    )
    p = build_llm_provider(cfg)
    assert isinstance(p, LLMProvider)


def test_factory_raises_for_unknown() -> None:
    cfg = LLMConfig(
        provider="router_9",
        base_url="https://x",
        api_key=SecretStr("k"),
        ranker_model="r",
        composer_model="c",
    )
    object.__setattr__(cfg, "provider", "bogus")
    with pytest.raises(ValueError, match="unknown llm provider"):
        build_llm_provider(cfg)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_llm_factory.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `src/ig_qt/llm/__init__.py`**

```python
"""LLM provider abstractions."""
from __future__ import annotations

from ig_qt.llm.base import LLMProvider, LLMResponse
from ig_qt.llm.factory import build_llm_provider

__all__ = ["LLMProvider", "LLMResponse", "build_llm_provider"]
```

- [ ] **Step 4: Implement `src/ig_qt/llm/base.py`**

```python
"""Provider-agnostic LLM interface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class LLMResponse:
    """Result of an LLM call."""

    content: str
    parsed: dict[str, Any] | None
    model: str
    input_tokens: int
    output_tokens: int


@runtime_checkable
class LLMProvider(Protocol):
    """Provider interface — implemented per backend."""

    name: str

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.4,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        """Run a chat completion that returns a JSON object."""
        ...

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.7,
        max_output_tokens: int = 1500,
    ) -> LLMResponse:
        """Run a plain-text chat completion."""
        ...
```

- [ ] **Step 5: Implement `src/ig_qt/llm/router_9.py`**

```python
"""9router adapter (assumes OpenAI-compatible /v1/chat/completions)."""
from __future__ import annotations

import json
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.llm.base import LLMResponse


class Router9Provider:
    """OpenAI-compatible adapter for 9router."""

    name = "router_9"

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.4,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        data = await self._post(payload)
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        try:
            parsed = json.loads(choice)
        except json.JSONDecodeError:
            parsed = None
        return LLMResponse(
            content=choice,
            parsed=parsed,
            model=model,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.7,
        max_output_tokens: int = 1500,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        data = await self._post(payload)
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice,
            parsed=None,
            model=model,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )
```

- [ ] **Step 6: Implement `src/ig_qt/llm/openai_provider.py`**

```python
"""Direct OpenAI adapter — same wire format as Router9 (subclass)."""
from __future__ import annotations

from ig_qt.llm.router_9 import Router9Provider


class OpenAIProvider(Router9Provider):
    """OpenAI is OpenAI-compatible by definition; reuse Router9 wire format."""

    name = "openai"
```

- [ ] **Step 7: Implement `src/ig_qt/llm/anthropic_provider.py`**

```python
"""Direct Anthropic adapter (Messages API)."""
from __future__ import annotations

import json
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.llm.base import LLMResponse


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/messages",
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.4,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": [{"role": "user", "content": user + "\n\nReply with JSON only."}],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        data = await self._post(payload)
        text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        return LLMResponse(
            content=text,
            parsed=parsed,
            model=model,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.7,
        max_output_tokens: int = 1500,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        data = await self._post(payload)
        text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        return LLMResponse(
            content=text,
            parsed=None,
            model=model,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )
```

- [ ] **Step 8: Implement `src/ig_qt/llm/gemini_provider.py`**

```python
"""Direct Gemini adapter (generateContent)."""
from __future__ import annotations

import json
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.llm.base import LLMResponse


class GeminiProvider:
    name = "gemini"

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _post(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/models/{model}:generateContent?key={self._api_key}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()

    def _build_payload(
        self, system: str, user: str, temperature: float, max_tokens: int, json_mode: bool
    ) -> dict[str, Any]:
        config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if json_mode:
            config["responseMimeType"] = "application/json"
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": config,
        }

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.4,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        payload = self._build_payload(system, user, temperature, max_output_tokens, json_mode=True)
        data = await self._post(model, payload)
        cand = data["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        usage = data.get("usageMetadata", {})
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        return LLMResponse(
            content=text,
            parsed=parsed,
            model=model,
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
        )

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.7,
        max_output_tokens: int = 1500,
    ) -> LLMResponse:
        payload = self._build_payload(system, user, temperature, max_output_tokens, json_mode=False)
        data = await self._post(model, payload)
        cand = data["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            content=text,
            parsed=None,
            model=model,
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
        )
```

- [ ] **Step 9: Implement `src/ig_qt/llm/factory.py`**

```python
"""Build a concrete LLMProvider from LLMConfig."""
from __future__ import annotations

from ig_qt.config import LLMConfig
from ig_qt.llm.anthropic_provider import AnthropicProvider
from ig_qt.llm.base import LLMProvider
from ig_qt.llm.gemini_provider import GeminiProvider
from ig_qt.llm.openai_provider import OpenAIProvider
from ig_qt.llm.router_9 import Router9Provider


def build_llm_provider(cfg: LLMConfig) -> LLMProvider:
    """Resolve config.provider → concrete adapter."""
    api_key = cfg.api_key.get_secret_value()
    timeout = float(cfg.request_timeout_seconds)

    if cfg.provider == "router_9":
        return Router9Provider(base_url=cfg.base_url, api_key=api_key, timeout=timeout)
    if cfg.provider == "openai":
        return OpenAIProvider(base_url=cfg.base_url, api_key=api_key, timeout=timeout)
    if cfg.provider == "anthropic":
        return AnthropicProvider(base_url=cfg.base_url, api_key=api_key, timeout=timeout)
    if cfg.provider == "gemini":
        return GeminiProvider(base_url=cfg.base_url, api_key=api_key, timeout=timeout)
    raise ValueError(f"unknown llm provider: {cfg.provider}")
```

- [ ] **Step 10: Run tests**

```bash
uv run pytest tests/test_llm_factory.py -v
```

Expected: PASS.

- [ ] **Step 11: Run mypy**

```bash
uv run mypy --strict src/ig_qt/llm/
```

Expected: `Success: no issues found`.

- [ ] **Step 12: Commit**

```bash
git add src/ig_qt/llm/ tests/test_llm_factory.py
git commit -m "feat(llm): add provider Protocol + factory with 4 backends"
```

---

## Task 1.7: Telegram notifier

**Files:**
- Create: `src/ig_qt/notifier.py`
- Create: `tests/test_notifier.py`

**Depends on:** OD-4 (Telegram bot reuse vs new) — plan assumes new bot, override via env var.

- [ ] **Step 1: Write failing test**

`tests/test_notifier.py`:

```python
"""Tests for Telegram notifier."""
from __future__ import annotations

import httpx
import pytest

from ig_qt.notifier import NoopNotifier, TelegramNotifier


@pytest.mark.asyncio
async def test_noop_notifier_does_nothing() -> None:
    n = NoopNotifier()
    await n.send("anything")  # should not raise


@pytest.mark.asyncio
async def test_telegram_notifier_posts_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_post(self, url: str, json: dict, **_):  # type: ignore[no-untyped-def]
        captured["url"] = url
        captured["json"] = json

        class R:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

        return R()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    n = TelegramNotifier(bot_token="token-x", chat_id="123")
    await n.send("hello")
    assert captured["url"] == "https://api.telegram.org/bottoken-x/sendMessage"
    assert captured["json"] == {"chat_id": "123", "text": "hello", "parse_mode": "Markdown"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_notifier.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `src/ig_qt/notifier.py`**

```python
"""Notifier abstractions: Telegram + no-op."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


@runtime_checkable
class Notifier(Protocol):
    async def send(self, message: str) -> None: ...


class NoopNotifier:
    """Used when notifications disabled."""

    async def send(self, message: str) -> None:
        logger.debug("notifier disabled, dropping message: {}", message[:200])


class TelegramNotifier:
    def __init__(self, *, bot_token: str, chat_id: str, timeout: float = 10.0) -> None:
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._chat_id = chat_id
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def send(self, message: str) -> None:
        # Truncate to Telegram limit (4096) with safety margin.
        text = message[:3900]
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url,
                json={"chat_id": self._chat_id, "text": text, "parse_mode": "Markdown"},
            )
            resp.raise_for_status()
        logger.info("telegram_notify_sent")


def build_notifier(*, enabled: bool, bot_token: str | None, chat_id: str | None) -> Notifier:
    if enabled and bot_token and chat_id:
        return TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    return NoopNotifier()
```

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/test_notifier.py -v
```

Expected: PASS.

- [ ] **Step 5: Run mypy**

```bash
uv run mypy --strict src/ig_qt/notifier.py
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add src/ig_qt/notifier.py tests/test_notifier.py
git commit -m "feat(notifier): add Telegram notifier with retry + noop fallback"
```

---

## Task 1.8: App bootstrap + `--check` command

**Files:**
- Create: `src/ig_qt/app.py`
- Modify: `src/ig_qt/__main__.py`
- Create: `tests/test_app.py`

- [ ] **Step 1: Write failing test**

`tests/test_app.py`:

```python
"""Tests for app bootstrap."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ig_qt.app import run_check


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "brand": {
                    "primary": "#000",
                    "accent": "#fff",
                    "font": "Inter",
                    "handle": "@x",
                    "logo_path": "assets/logo.png",
                },
                "llm": {
                    "provider": "router_9",
                    "base_url_env": "LLM_BASE_URL",
                    "api_key_env": "LLM_API_KEY",
                    "models": {"ranker": "r", "composer": "c"},
                    "request_timeout_seconds": 30,
                    "max_retries": 2,
                },
                "schedule": {
                    "timezone": "Asia/Jakarta",
                    "feed_post_hour": 11,
                    "feed_post_jitter_minutes": 15,
                    "story_event_hour": 12,
                    "story_recap_hour": 21,
                    "skip_day_probability": 0.14,
                    "posting_window_start_hour": 6,
                    "posting_window_end_hour": 23,
                },
                "ig": {
                    "username_env": "IG_USERNAME",
                    "password_env": "IG_PASSWORD",
                    "max_feed_per_day": 2,
                    "max_feed_per_week": 10,
                    "max_story_per_day": 5,
                    "max_login_per_day": 1,
                    "delay_range_seconds": [2, 5],
                },
                "collector": {
                    "news_api_enabled": False,
                    "news_api_key_env": "NEWSAPI_KEY",
                    "gnews_enabled": False,
                    "gnews_key_env": "GNEWS_KEY",
                    "twelve_data_enabled": False,
                    "twelve_data_key_env": "TWELVEDATA_KEY",
                    "forex_factory_enabled": False,
                    "symbols": [],
                },
                "notifier": {
                    "telegram_enabled": False,
                    "telegram_bot_token_env": "TELEGRAM_BOT_TOKEN",
                    "telegram_chat_id_env": "TELEGRAM_CHAT_ID",
                },
                "paths": {
                    "data_dir_env": "IG_QT_DATA_DIR",
                    "data_dir_default": str(tmp_path / "data"),
                },
            }
        ),
        encoding="utf-8",
    )
    return p


def test_run_check_returns_zero_on_valid_config(
    config_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("IG_USERNAME", "u")
    monkeypatch.setenv("IG_PASSWORD", "p")
    monkeypatch.setenv("IG_QT_DATA_DIR", str(tmp_path / "data"))
    rc = run_check(config_path=config_path)
    assert rc == 0
    assert (tmp_path / "data" / "ig_qt.db").exists()
```

- [ ] **Step 2: Implement `src/ig_qt/app.py`**

```python
"""Application bootstrap."""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from ig_qt.config import load_config
from ig_qt.db import build_engine, init_schema
from ig_qt.llm.factory import build_llm_provider
from ig_qt.logging_setup import configure_logging
from ig_qt.notifier import build_notifier


def run_check(*, config_path: Path) -> int:
    """Validate environment + initialize DB schema. Returns process exit code."""
    cfg = load_config(config_path)
    log_dir = cfg.paths.data_dir / "logs"
    configure_logging(log_dir=log_dir, level="INFO", json_logs=True)
    logger.info("config_loaded provider={} tz={}", cfg.llm.provider, cfg.schedule.timezone)

    db_path = cfg.paths.data_dir / "ig_qt.db"
    engine = build_engine(db_path)
    init_schema(engine)
    logger.info("db_ready path={}", db_path)

    # Build (but do not invoke) provider + notifier — proves config wiring works.
    provider = build_llm_provider(cfg.llm)
    logger.info("llm_provider_ready name={}", provider.name)
    notifier = build_notifier(
        enabled=cfg.notifier.telegram_enabled,
        bot_token=(
            cfg.notifier.telegram_bot_token.get_secret_value()
            if cfg.notifier.telegram_bot_token
            else None
        ),
        chat_id=cfg.notifier.telegram_chat_id,
    )
    logger.info("notifier_ready type={}", type(notifier).__name__)
    return 0
```

- [ ] **Step 3: Update `src/ig_qt/__main__.py`**

```python
"""Entry point: `python -m ig_qt`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ig_qt.app import run_check


def main() -> int:
    parser = argparse.ArgumentParser(prog="ig_qt")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate env + initialize DB and exit",
    )
    args = parser.parse_args()
    if args.check:
        return run_check(config_path=args.config)
    print("ig_qt: scheduler entry point not implemented yet (M5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest -v
```

Expected: ALL PASS.

- [ ] **Step 5: Manual smoke test**

```bash
cp .env.example .env
# fill at minimum: LLM_BASE_URL, LLM_API_KEY, IG_USERNAME, IG_PASSWORD
uv run python -m ig_qt --check
```

Expected: log lines `config_loaded`, `db_ready`, `llm_provider_ready`, `notifier_ready`. `data/ig_qt.db` exists.

- [ ] **Step 6: Run full mypy**

```bash
uv run mypy --strict src/
```

Expected: `Success: no issues found`.

- [ ] **Step 7: Run ruff**

```bash
uv run ruff check src/ tests/
```

Expected: no errors. Fix any reported issue.

- [ ] **Step 8: Commit**

```bash
git add src/ig_qt/app.py src/ig_qt/__main__.py tests/test_app.py
git commit -m "feat(app): wire bootstrap and --check command"
```

---

## M1 Acceptance Criteria

Before moving to M2, verify all of these:

- [ ] `uv run pytest -v` all green, coverage ≥80% for changed files
- [ ] `uv run mypy --strict src/` clean
- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run python -m ig_qt --check` exits 0 and logs all 4 readiness lines
- [ ] `data/ig_qt.db` created with all tables: `raw_news`, `events`, `prices_cache`, `post_drafts`, `posts`, `publish_log`, `ig_account_state`, `posted_topics`
- [ ] No secrets logged (grep `data/logs/app.log` for `LLM_API_KEY` value, `IG_PASSWORD`, etc — should not appear)
- [ ] All 8 tasks committed individually with conventional commit messages

## M1 Self-Review Notes

- LLM factory: `complete_json` returns `parsed=None` when JSON malformed — analyst layer (M3) will retry on `parsed is None`. Don't add retry inside factory.
- `Router9Provider` and `OpenAIProvider` share identical wire format. Keep as separate classes for clarity (provider name in logs/metrics) and future divergence.
- DB `created_at` defaults to `datetime.now(timezone.utc)` — always UTC in DB. Schedule timezone (`Asia/Jakarta`) only for cron triggers + display.
- `session_scope` rolls back on any exception, then re-raises. Caller decides whether to swallow.
- Telegram notifier truncates to 3900 chars (Telegram hard limit 4096, safety margin for Markdown overhead).
