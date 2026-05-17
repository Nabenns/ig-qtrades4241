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
