"""Application bootstrap."""
from __future__ import annotations

from datetime import UTC, datetime
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


async def run_collect_once(*, config_path: Path) -> int:
    """One-shot collector run for manual invocation / testing."""
    from ig_qt.collector.pipeline import build_pipeline_from_config

    cfg = load_config(config_path)
    log_dir = cfg.paths.data_dir / "logs"
    configure_logging(log_dir=log_dir, level="INFO", json_logs=True)
    db_path = cfg.paths.data_dir / "ig_qt.db"
    engine = build_engine(db_path)
    init_schema(engine)
    pipeline = build_pipeline_from_config(engine, cfg)
    result = await pipeline.run_once()
    logger.info(
        "collect_done news={} events={} failed={}",
        result.news_inserted,
        result.events_inserted,
        result.failed_sources,
    )
    return 0 if not result.failed_sources else 1


async def run_analyze_once(*, config_path: Path) -> int:
    """One-shot analyst run for manual invocation / testing."""
    from ig_qt.analyst.runner import AnalystRunner

    cfg = load_config(config_path)
    log_dir = cfg.paths.data_dir / "logs"
    configure_logging(log_dir=log_dir, level="INFO", json_logs=True)
    engine = build_engine(cfg.paths.data_dir / "ig_qt.db")
    init_schema(engine)
    provider = build_llm_provider(cfg.llm)
    runner = AnalystRunner(
        engine=engine,
        provider=provider,
        ranker_model=cfg.llm.ranker_model,
        composer_model=cfg.llm.composer_model,
        story_count=3,
        confidence_threshold=0.6,
    )
    summary = await runner.run_once(today=datetime.now(UTC))
    logger.info(
        "analyze_done feed={} story={} evergreen={} rejected={}",
        summary.feed_drafts,
        summary.story_drafts,
        summary.evergreen_used,
        summary.rejected_low_confidence,
    )
    return 0 if (summary.feed_drafts + summary.story_drafts) > 0 else 2
