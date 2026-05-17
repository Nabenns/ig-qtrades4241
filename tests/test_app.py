"""Tests for app bootstrap."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ig_qt.app import run_check


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "brand": {
                    "primary": "#000",
                    "accent": "#fff",
                    "font": "Inter",
                    "handle": "@x",
                    "logo_path": "assets/logo.png",
                },
                "llm": {
                    "provider": "router_9",
                    "base_url_env": "LLM_BASE_URL",
                    "api_key_env": "LLM_API_KEY",
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
                    "username_env": "IG_USERNAME",
                    "password_env": "IG_PASSWORD",
                    "max_feed_per_day": 2,
                    "max_feed_per_week": 10,
                    "max_story_per_day": 5,
                    "max_login_per_day": 1,
                    "delay_range_seconds": [2, 5],
                },
                "collector": {
                    "news_api_enabled": False,
                    "news_api_key_env": "NEWSAPI_KEY",
                    "gnews_enabled": False,
                    "gnews_key_env": "GNEWS_KEY",
                    "twelve_data_enabled": False,
                    "twelve_data_key_env": "TWELVEDATA_KEY",
                    "forex_factory_enabled": False,
                    "symbols": [],
                },
                "notifier": {
                    "telegram_enabled": False,
                    "telegram_bot_token_env": "TELEGRAM_BOT_TOKEN",
                    "telegram_chat_id_env": "TELEGRAM_CHAT_ID",
                },
                "paths": {
                    "data_dir_env": "IG_QT_DATA_DIR",
                    "data_dir_default": str(tmp_path / "data"),
                },
            }
        ),
        encoding="utf-8",
    )
    return p


def test_run_check_returns_zero_on_valid_config(
    config_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("IG_USERNAME", "u")
    monkeypatch.setenv("IG_PASSWORD", "p")
    monkeypatch.setenv("IG_QT_DATA_DIR", str(tmp_path / "data"))
    rc = run_check(config_path=config_path)
    assert rc == 0
    assert (tmp_path / "data" / "ig_qt.db").exists()
