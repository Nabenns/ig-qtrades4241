"""One-shot pipeline: collect → analyze → compose → send Telegram review.

Run: uv run python scripts/run_pipeline.py

Use this when you want to manually kick off the whole flow without running the
scheduler daemon. Each phase prints a summary; the script exits non-zero if
nothing reaches the review queue.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from loguru import logger

from ig_qt.analyst.runner import AnalystRunner
from ig_qt.collector.pipeline import build_pipeline_from_config
from ig_qt.composer.image_critic import build_image_critic
from ig_qt.composer.image_gen import build_image_gen
from ig_qt.composer.runner import ComposerRunner
from ig_qt.config import load_config
from ig_qt.db import build_engine, init_schema
from ig_qt.llm.factory import build_llm_provider
from ig_qt.logging_setup import configure_logging
from ig_qt.models import PostDraft
from ig_qt.notifier import build_notifier
from ig_qt.notifier_review import build_reviewer, send_pending_reviews
from ig_qt.pipeline_health import (
    alert_analyst_if_degraded,
    alert_collect_if_degraded,
)


def _banner(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


async def _main(skip_collect: bool, skip_analyze: bool, skip_compose: bool) -> int:
    cfg = load_config(Path("config.yaml"))
    log_dir = cfg.paths.data_dir / "logs"
    configure_logging(log_dir=log_dir, level="INFO", json_logs=False)
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

    # ── Phase 1: collect ────────────────────────────────────────────────
    if not skip_collect:
        _banner("Phase 1/4 — Collect news + events")
        pipeline = build_pipeline_from_config(engine, cfg)
        result = await pipeline.run_once()
        logger.info(
            "collect_done news={} events={} failed={}",
            result.news_inserted,
            result.events_inserted,
            result.failed_sources,
        )
        await alert_collect_if_degraded(notifier=notifier, result=result, engine=engine)
    else:
        _banner("Phase 1/4 — Collect SKIPPED (--skip-collect)")

    # ── Phase 2: analyze ────────────────────────────────────────────────
    if not skip_analyze:
        _banner("Phase 2/4 — Analyze (rank + draft)")
        provider = build_llm_provider(cfg.llm)
        analyst = AnalystRunner(
            engine=engine,
            provider=provider,
            ranker_model=cfg.llm.ranker_model,
            composer_model=cfg.llm.composer_model,
            story_count=3,
            confidence_threshold=0.6,
        )
        summary = await analyst.run_once(today=datetime.now(UTC))
        logger.info(
            "analyze_done feed={} story={} evergreen={} rejected={} stale={}",
            summary.feed_drafts,
            summary.story_drafts,
            summary.evergreen_used,
            summary.rejected_low_confidence,
            summary.stale_inputs,
        )
        await alert_analyst_if_degraded(notifier=notifier, summary=summary, engine=engine)
        if summary.feed_drafts + summary.story_drafts == 0:
            logger.error("analyze produced 0 drafts — aborting pipeline")
            return 2
    else:
        _banner("Phase 2/4 — Analyze SKIPPED (--skip-analyze)")

    # ── Phase 3: compose ────────────────────────────────────────────────
    if not skip_compose:
        _banner("Phase 3/4 — Compose (image gen + render)")
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
        comp_summary = await composer.run_once()
        logger.info(
            "compose_done processed={} failed={}",
            comp_summary.processed,
            comp_summary.failed,
        )
    else:
        _banner("Phase 3/4 — Compose SKIPPED (--skip-compose)")

    # ── Phase 4: send Telegram review ───────────────────────────────────
    _banner("Phase 4/4 — Send Telegram review")
    reviewer = build_reviewer(
        enabled=cfg.notifier.telegram_enabled,
        bot_token=(
            cfg.notifier.telegram_bot_token.get_secret_value()
            if cfg.notifier.telegram_bot_token
            else None
        ),
        chat_id=cfg.notifier.telegram_chat_id,
    )
    if reviewer is None:
        logger.error(
            "telegram_disabled_or_misconfigured — set "
            "TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID"
        )
        return 3
    sent = await send_pending_reviews(engine=engine, reviewer=reviewer)
    logger.info("review_send_total sent={}", sent)
    print()
    print("=" * 60)
    print(f"  Pipeline done. Reviews sent to Telegram: {sent}")
    print("=" * 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-shot ig-qt pipeline: collect → analyze → compose → telegram review",
    )
    parser.add_argument("--skip-collect", action="store_true")
    parser.add_argument("--skip-analyze", action="store_true")
    parser.add_argument("--skip-compose", action="store_true")
    args = parser.parse_args()
    return asyncio.run(
        _main(
            skip_collect=args.skip_collect,
            skip_analyze=args.skip_analyze,
            skip_compose=args.skip_compose,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
