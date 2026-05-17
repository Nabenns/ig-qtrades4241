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
