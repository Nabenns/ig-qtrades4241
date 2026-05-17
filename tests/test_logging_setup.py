"""Tests for logging setup."""
from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from ig_qt.logging_setup import configure_logging


def test_configure_logging_writes_json_to_file(tmp_path: Path) -> None:
    log_file = tmp_path / "app.log"
    configure_logging(log_dir=tmp_path, level="INFO", json_logs=True)
    logger.info("hello")
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
