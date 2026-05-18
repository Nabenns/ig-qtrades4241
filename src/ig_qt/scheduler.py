"""APScheduler setup with persistent SQLite jobstore."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from ig_qt.config import AppConfig


def build_jobs_spec(cfg: AppConfig) -> list[dict[str, Any]]:
    """Pure function: returns job spec table without scheduling.

    Useful for tests + observability.
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
                hour=sched.feed_post_hour,
                minute=0,
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
    return AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{jobs_db}")},
        timezone=cfg.schedule.timezone,
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 600},
    )


def attach_jobs(
    scheduler: AsyncIOScheduler,
    *,
    cfg: AppConfig,
    handlers: Mapping[str, Callable[[], Awaitable[Any]]],
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
