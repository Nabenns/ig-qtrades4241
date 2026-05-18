"""Application bootstrap."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


async def run_compose_once(*, config_path: Path) -> int:
    """One-shot composer run: process pending drafts into ready posts."""
    from ig_qt.composer.image_critic import build_image_critic
    from ig_qt.composer.image_gen import build_image_gen
    from ig_qt.composer.runner import ComposerRunner
    from ig_qt.models import PostDraft

    cfg = load_config(config_path)
    log_dir = cfg.paths.data_dir / "logs"
    configure_logging(log_dir=log_dir, level="INFO", json_logs=True)
    engine = build_engine(cfg.paths.data_dir / "ig_qt.db")
    init_schema(engine)

    feed_hour = cfg.schedule.feed_post_hour

    def _sched_for(d: PostDraft) -> datetime:
        now = datetime.now(UTC)
        if d.post_type == "feed":
            return now.replace(hour=feed_hour, minute=0, second=0, microsecond=0)
        return now + timedelta(minutes=30)

    image_gen = build_image_gen(
        enabled=cfg.image_gen.enabled,
        provider=cfg.image_gen.provider,
        router_base_url=cfg.llm.base_url,
        router_api_key=cfg.llm.api_key.get_secret_value(),
        router_model=cfg.image_gen.model,
        cf_account_id=cfg.image_gen.account_id,
        cf_api_token=(
            cfg.image_gen.api_token.get_secret_value()
            if cfg.image_gen.api_token
            else None
        ),
    )
    image_critic = build_image_critic(
        enabled=cfg.image_gen.enabled,
        base_url=cfg.llm.base_url,
        api_key=cfg.llm.api_key.get_secret_value(),
    )
    runner = ComposerRunner(
        engine=engine,
        data_dir=cfg.paths.data_dir,
        logo_path=Path(cfg.brand.logo_path),
        handle=cfg.brand.handle,
        scheduled_for_factory=_sched_for,
        image_gen=image_gen,
        image_critic=image_critic,
    )
    summary = await runner.run_once()
    logger.info("compose_done processed={} failed={}", summary.processed, summary.failed)
    return 0 if summary.failed == 0 else 1


def run_admin(*, config_path: Path, admin_cmd: str | None) -> int:
    """Operational admin commands: warmup-status, warmup-enable, warmup-disable."""
    from sqlalchemy import select

    from ig_qt.admin.warmup_mode import (
        assess_readiness,
        disable_warmup,
        enable_warmup,
    )
    from ig_qt.db import session_scope as _ss
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
        with _ss(engine) as s:
            state = s.execute(select(IGAccountState).limit(1)).scalar_one_or_none()
            if state is None:
                print("No account state row yet — run --check or any pipeline first.")
                return 1
            status = assess_readiness(state, now=datetime.now(UTC))
        print(f"warmup_active:    {status.warmup_active}")
        print(f"warmup_started:   {status.warmup_started_at}")
        print(f"days_in_warmup:   {status.days_in_warmup}")
        print(f"last_post_at:     {status.last_post_at}")
        if status.warmup_active and status.days_in_warmup >= 14:
            print("Recommend running: admin warmup-disable")
        elif status.warmup_active:
            print(f"Continue warmup ({14 - status.days_in_warmup} days remaining)")
        return 0
    print("Unknown admin command. Try: warmup-status, warmup-enable, warmup-disable")
    return 2


async def run_long_running(*, config_path: Path) -> int:
    """Long-running orchestrator: APScheduler + /health endpoint together."""
    import uvicorn

    from ig_qt import __version__
    from ig_qt.analyst.runner import AnalystRunner
    from ig_qt.collector.pipeline import build_pipeline_from_config
    from ig_qt.composer.image_critic import build_image_critic
    from ig_qt.composer.image_gen import build_image_gen
    from ig_qt.composer.runner import ComposerRunner
    from ig_qt.health import build_health_app
    from ig_qt.models import PostDraft
    from ig_qt.publisher.ig_client import IGClient
    from ig_qt.publisher.rate_limiter import offset_hours_for_timezone
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
        engine=engine,
        provider=provider,
        ranker_model=cfg.llm.ranker_model,
        composer_model=cfg.llm.composer_model,
    )

    feed_hour = cfg.schedule.feed_post_hour

    def _sched_for(d: PostDraft) -> datetime:
        now = datetime.now(UTC)
        if d.post_type == "feed":
            return now.replace(hour=feed_hour, minute=0, second=0, microsecond=0)
        return now + timedelta(minutes=30)

    image_gen = build_image_gen(
        enabled=cfg.image_gen.enabled,
        provider=cfg.image_gen.provider,
        router_base_url=cfg.llm.base_url,
        router_api_key=cfg.llm.api_key.get_secret_value(),
        router_model=cfg.image_gen.model,
        cf_account_id=cfg.image_gen.account_id,
        cf_api_token=(
            cfg.image_gen.api_token.get_secret_value()
            if cfg.image_gen.api_token
            else None
        ),
    )
    image_critic = build_image_critic(
        enabled=cfg.image_gen.enabled,
        base_url=cfg.llm.base_url,
        api_key=cfg.llm.api_key.get_secret_value(),
    )
    composer = ComposerRunner(
        engine=engine,
        data_dir=cfg.paths.data_dir,
        logo_path=Path(cfg.brand.logo_path),
        handle=cfg.brand.handle,
        scheduled_for_factory=_sched_for,
        image_gen=image_gen,
        image_critic=image_critic,
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
        tz_offset_hours=offset_hours_for_timezone(cfg.schedule.timezone),
        skip_day_seed=cfg.ig.username,
        skip_day_probability=cfg.schedule.skip_day_probability,
        warmup_seed=42,
    )

    pipeline = build_pipeline_from_config(engine, cfg)

    async def collect_news() -> None:
        await pipeline.run_once()

    async def collect_calendar() -> None:
        await pipeline.run_once()

    async def analyst_job() -> None:
        await analyst.run_once(today=datetime.now(UTC))

    async def composer_job() -> None:
        await composer.run_once()

    async def publisher_job() -> None:
        await publisher.run_due()

    async def story_event_job() -> None:
        await generate_event_reminder_story(
            engine=engine,
            data_dir=cfg.paths.data_dir,
            logo_path=Path(cfg.brand.logo_path),
            handle=cfg.brand.handle,
            scheduled_for=datetime.now(UTC),
        )

    async def story_recap_job() -> None:
        await generate_market_recap_story(
            engine=engine,
            data_dir=cfg.paths.data_dir,
            logo_path=Path(cfg.brand.logo_path),
            handle=cfg.brand.handle,
            scheduled_for=datetime.now(UTC),
            symbols=cfg.collector.symbols,
        )

    async def audit_job() -> None:
        from ig_qt.audit import audit_recent_posts, format_audit_report

        flags = audit_recent_posts(engine, days=7)
        report = format_audit_report(flags)
        await notifier.send(report)

    async def cleanup_job() -> None:
        from ig_qt.admin.cleanup import cleanup_old_assets

        cleanup_old_assets(engine, posts_dir=cfg.paths.data_dir / "posts", age_days=30)

    handlers = {
        "collect_news_morning": collect_news,
        "collect_news_evening": collect_news,
        "ff_calendar_weekly": collect_calendar,
        "analyst_daily": analyst_job,
        "composer_loop": composer_job,
        "publisher_loop": publisher_job,
        "story_event_reminder": story_event_job,
        "story_market_recap": story_recap_job,
        "weekly_audit": audit_job,
        "weekly_cleanup": cleanup_job,
    }

    scheduler = build_scheduler(cfg=cfg, jobs_db=cfg.paths.data_dir / "jobs.db")
    attach_jobs(scheduler, cfg=cfg, handlers=handlers)
    scheduler.start()
    logger.info("scheduler_started")

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

    try:
        await server.serve()
    finally:
        scheduler.shutdown(wait=True)
    return 0
