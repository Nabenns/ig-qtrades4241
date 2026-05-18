"""Tests for scheduler config building."""
from __future__ import annotations

from pathlib import Path

import yaml

from ig_qt.config import load_config
from ig_qt.scheduler import build_jobs_spec


def test_build_jobs_spec_includes_all_required(
    tmp_path: Path, monkeypatch: object
) -> None:
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "brand": {
                    "primary": "#0",
                    "accent": "#0",
                    "font": "Inter",
                    "handle": "@x",
                    "logo_path": "assets/logo.png",
                },
                "llm": {
                    "provider": "router_9",
                    "base_url_env": "L_B",
                    "api_key_env": "L_K",
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
                    "username_env": "U",
                    "password_env": "P",
                    "max_feed_per_day": 2,
                    "max_feed_per_week": 10,
                    "max_story_per_day": 5,
                    "max_login_per_day": 1,
                    "delay_range_seconds": [2, 5],
                },
                "collector": {
                    "news_api_enabled": False,
                    "news_api_key_env": "NA",
                    "gnews_enabled": False,
                    "gnews_key_env": "GN",
                    "twelve_data_enabled": False,
                    "twelve_data_key_env": "TD",
                    "forex_factory_enabled": False,
                    "symbols": [],
                },
                "notifier": {
                    "telegram_enabled": False,
                    "telegram_bot_token_env": "T",
                    "telegram_chat_id_env": "TC",
                },
                "paths": {
                    "data_dir_env": "DD",
                    "data_dir_default": str(tmp_path),
                },
            }
        )
    )
    import os

    os.environ.update({"L_B": "x", "L_K": "x", "U": "u", "P": "p"})
    cfg = load_config(cfg_path)
    spec = build_jobs_spec(cfg)
    job_ids = {j["id"] for j in spec}
    assert "collect_news_morning" in job_ids
    assert "collect_news_evening" in job_ids
    assert "ff_calendar_weekly" in job_ids
    assert "analyst_daily" in job_ids
    assert "composer_loop" in job_ids
    assert "publisher_loop" in job_ids
    assert "story_event_reminder" in job_ids
    assert "story_market_recap" in job_ids
