"""Tests for config loader."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ig_qt.config import AppConfig, load_config


@pytest.fixture
def yaml_path(tmp_path: Path) -> Path:
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
                    "news_api_enabled": True,
                    "news_api_key_env": "NEWSAPI_KEY",
                    "gnews_enabled": True,
                    "gnews_key_env": "GNEWS_KEY",
                    "twelve_data_enabled": True,
                    "twelve_data_key_env": "TWELVEDATA_KEY",
                    "forex_factory_enabled": True,
                    "symbols": ["EUR/USD"],
                },
                "notifier": {
                    "telegram_enabled": True,
                    "telegram_bot_token_env": "TELEGRAM_BOT_TOKEN",
                    "telegram_chat_id_env": "TELEGRAM_CHAT_ID",
                },
                "paths": {
                    "data_dir_env": "IG_QT_DATA_DIR",
                    "data_dir_default": "data",
                },
            }
        ),
        encoding="utf-8",
    )
    return p


def test_load_config_returns_app_config(yaml_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("IG_USERNAME", "u")
    monkeypatch.setenv("IG_PASSWORD", "p")
    monkeypatch.setenv("NEWSAPI_KEY", "n")
    monkeypatch.setenv("GNEWS_KEY", "g")
    monkeypatch.setenv("TWELVEDATA_KEY", "t")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "b")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    cfg = load_config(yaml_path)
    assert isinstance(cfg, AppConfig)
    assert cfg.llm.provider == "router_9"
    assert cfg.llm.api_key.get_secret_value() == "k"
    assert cfg.ig.password.get_secret_value() == "p"
    assert cfg.schedule.feed_post_hour == 11
    assert cfg.collector.symbols == ["EUR/USD"]


def test_load_config_missing_required_secret_fails(
    yaml_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://x")
    monkeypatch.setenv("IG_USERNAME", "u")
    monkeypatch.setenv("IG_PASSWORD", "p")
    monkeypatch.setenv("NEWSAPI_KEY", "n")
    monkeypatch.setenv("GNEWS_KEY", "g")
    monkeypatch.setenv("TWELVEDATA_KEY", "t")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "b")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        load_config(yaml_path)
