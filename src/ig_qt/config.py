"""Application configuration loaded from config.yaml + environment."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


def _load_dotenv_if_present(env_path: Path = Path(".env")) -> None:
    """Lightweight .env loader (no dotenv dependency). Sets os.environ keys not already set."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv_if_present()


class BrandConfig(BaseModel):
    primary: str
    accent: str
    font: str
    handle: str
    logo_path: str


class LLMConfig(BaseModel):
    provider: Literal["router_9", "openai", "anthropic", "gemini"]
    base_url: str
    api_key: SecretStr
    ranker_model: str
    composer_model: str
    request_timeout_seconds: int = 30
    max_retries: int = 2


class ScheduleConfig(BaseModel):
    timezone: str
    feed_post_hour: int
    feed_post_jitter_minutes: int
    story_event_hour: int
    story_recap_hour: int
    skip_day_probability: float = Field(ge=0.0, le=1.0)
    posting_window_start_hour: int = Field(ge=0, le=23)
    posting_window_end_hour: int = Field(ge=0, le=23)


class IGConfig(BaseModel):
    username: str
    password: SecretStr
    max_feed_per_day: int
    max_feed_per_week: int
    max_story_per_day: int
    max_login_per_day: int
    delay_range_seconds: tuple[float, float]

    @field_validator("delay_range_seconds", mode="before")
    @classmethod
    def _coerce_delay(cls, v: object) -> tuple[float, float]:
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return (float(v[0]), float(v[1]))
        raise ValueError("delay_range_seconds must be 2-element list")


class CollectorConfig(BaseModel):
    news_api_enabled: bool
    news_api_key: SecretStr | None
    gnews_enabled: bool
    gnews_key: SecretStr | None
    twelve_data_enabled: bool
    twelve_data_key: SecretStr | None
    forex_factory_enabled: bool
    rss_enabled: bool = True
    symbols: list[str]


class NotifierConfig(BaseModel):
    telegram_enabled: bool
    telegram_bot_token: SecretStr | None
    telegram_chat_id: str | None


class ImageGenConfig(BaseModel):
    enabled: bool
    provider: str = "router_9"  # router_9 | cloudflare
    model: str = "cf/@cf/black-forest-labs/flux-1-schnell"
    # Cloudflare-direct fields (only when provider=cloudflare)
    account_id: str | None = None
    api_token: SecretStr | None = None


class PathsConfig(BaseModel):
    data_dir: Path


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    brand: BrandConfig
    llm: LLMConfig
    schedule: ScheduleConfig
    ig: IGConfig
    collector: CollectorConfig
    notifier: NotifierConfig
    image_gen: ImageGenConfig
    paths: PathsConfig


def _require_env(var: str) -> str:
    val = os.environ.get(var)
    if not val:
        raise ValueError(f"required env var missing: {var}")
    return val


def _optional_env(var: str) -> str | None:
    return os.environ.get(var) or None


def load_config(yaml_path: Path) -> AppConfig:
    """Load config.yaml and resolve env-backed secrets."""
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

    llm_raw = raw["llm"]
    llm = LLMConfig(
        provider=llm_raw["provider"],
        base_url=_require_env(llm_raw["base_url_env"]),
        api_key=SecretStr(_require_env(llm_raw["api_key_env"])),
        ranker_model=llm_raw["models"]["ranker"],
        composer_model=llm_raw["models"]["composer"],
        request_timeout_seconds=llm_raw.get("request_timeout_seconds", 30),
        max_retries=llm_raw.get("max_retries", 2),
    )

    ig_raw = raw["ig"]
    ig = IGConfig(
        username=_require_env(ig_raw["username_env"]),
        password=SecretStr(_require_env(ig_raw["password_env"])),
        max_feed_per_day=ig_raw["max_feed_per_day"],
        max_feed_per_week=ig_raw["max_feed_per_week"],
        max_story_per_day=ig_raw["max_story_per_day"],
        max_login_per_day=ig_raw["max_login_per_day"],
        delay_range_seconds=tuple(ig_raw["delay_range_seconds"]),
    )

    coll_raw = raw["collector"]

    def _coll_secret(key: str, enabled_key: str) -> SecretStr | None:
        if not coll_raw.get(enabled_key):
            return None
        env_var = coll_raw.get(key)
        if not env_var:
            return None
        val = _optional_env(env_var)
        if val is None:
            raise ValueError(f"required env var missing: {env_var}")
        return SecretStr(val)

    collector = CollectorConfig(
        news_api_enabled=coll_raw["news_api_enabled"],
        news_api_key=_coll_secret("news_api_key_env", "news_api_enabled"),
        gnews_enabled=coll_raw["gnews_enabled"],
        gnews_key=_coll_secret("gnews_key_env", "gnews_enabled"),
        twelve_data_enabled=coll_raw["twelve_data_enabled"],
        twelve_data_key=_coll_secret("twelve_data_key_env", "twelve_data_enabled"),
        forex_factory_enabled=coll_raw["forex_factory_enabled"],
        rss_enabled=coll_raw.get("rss_enabled", True),
        symbols=list(coll_raw["symbols"]),
    )

    notif_raw = raw["notifier"]
    if notif_raw["telegram_enabled"]:
        notifier = NotifierConfig(
            telegram_enabled=True,
            telegram_bot_token=SecretStr(_require_env(notif_raw["telegram_bot_token_env"])),
            telegram_chat_id=_require_env(notif_raw["telegram_chat_id_env"]),
        )
    else:
        notifier = NotifierConfig(
            telegram_enabled=False, telegram_bot_token=None, telegram_chat_id=None
        )

    img_raw = raw.get("image_gen", {})
    if img_raw.get("enabled"):
        provider = img_raw.get("provider", "router_9")
        model = img_raw.get("model", "cf/@cf/black-forest-labs/flux-1-schnell")
        if provider == "cloudflare":
            account_id = _optional_env(img_raw["account_id_env"])
            token_val = _optional_env(img_raw["api_token_env"])
            image_gen = ImageGenConfig(
                enabled=True,
                provider=provider,
                model=model,
                account_id=account_id,
                api_token=SecretStr(token_val) if token_val else None,
            )
        else:  # router_9 (default) — reuses LLM_BASE_URL/LLM_API_KEY
            image_gen = ImageGenConfig(
                enabled=True,
                provider=provider,
                model=model,
                account_id=None,
                api_token=None,
            )
    else:
        image_gen = ImageGenConfig(enabled=False)

    paths_raw = raw["paths"]
    data_dir = Path(
        os.environ.get(paths_raw["data_dir_env"], paths_raw["data_dir_default"])
    ).resolve()

    return AppConfig(
        brand=BrandConfig(**raw["brand"]),
        llm=llm,
        schedule=ScheduleConfig(**raw["schedule"]),
        ig=ig,
        collector=collector,
        notifier=notifier,
        image_gen=image_gen,
        paths=PathsConfig(data_dir=data_dir),
    )
