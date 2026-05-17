"""Centralized Loguru configuration."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import Record

# Patterns that look like secrets in log lines.
_SECRET_PATTERNS = [
    re.compile(r"(api_key=)([A-Za-z0-9_\-\.]+)"),
    re.compile(r"(password=)(\S+)"),
    re.compile(r"(token=)([A-Za-z0-9_\-\.]+)"),
    re.compile(r"(Bearer\s+)([A-Za-z0-9_\-\.]+)", re.IGNORECASE),
]


def _redact_message(msg: str) -> str:
    for pat in _SECRET_PATTERNS:
        msg = pat.sub(r"\1[REDACTED]", msg)
    return msg


def _patcher(record: Record) -> None:
    record["message"] = _redact_message(record["message"])


def configure_logging(
    *,
    log_dir: Path,
    level: str = "INFO",
    json_logs: bool = True,
) -> None:
    """Configure Loguru sinks: stderr (human) + file (JSON or text)."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()

    logger.configure(patcher=_patcher)

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
