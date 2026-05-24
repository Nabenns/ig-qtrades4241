"""Seed the evergreen_drafts pool with 10 curated educational posts.

Run: uv run python scripts/seed_evergreen.py

Idempotent: skips drafts whose topic_tag already exists.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make sibling _evergreen_seeds module importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _evergreen_seeds import EVERGREEN_SEEDS
from loguru import logger
from pydantic import TypeAdapter
from sqlalchemy import select

from ig_qt.analyst.evergreen import store_evergreen_drafts
from ig_qt.analyst.schemas import AngleDraft
from ig_qt.config import load_config
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.logging_setup import configure_logging
from ig_qt.models import EvergreenDraft


def main() -> int:
    cfg = load_config(Path("config.yaml"))
    configure_logging(log_dir=cfg.paths.data_dir / "logs", level="INFO", json_logs=False)
    engine = build_engine(cfg.paths.data_dir / "ig_qt.db")
    init_schema(engine)

    drafts = TypeAdapter(list[AngleDraft]).validate_python(EVERGREEN_SEEDS)
    logger.info("evergreen_seeds_validated count={}", len(drafts))

    with session_scope(engine) as s:
        existing_tags = set(
            s.execute(select(EvergreenDraft.topic_tag)).scalars().all()
        )
        new_drafts = [d for d in drafts if d.topic_tag not in existing_tags]
        if not new_drafts:
            logger.info("evergreen_seed_skip_all_present count={}", len(drafts))
            return 0
        store_evergreen_drafts(s, new_drafts)
        logger.info(
            "evergreen_seed_done inserted={} skipped={}",
            len(new_drafts),
            len(drafts) - len(new_drafts),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
