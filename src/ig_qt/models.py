"""SQLAlchemy ORM models."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON, Mapping[str, Any]: JSON}


class RawNews(Base):
    __tablename__ = "raw_news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str | None] = mapped_column(String(256))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[Any] | None] = mapped_column(JSON)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    dedup_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    country: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(Text)
    impact: Mapped[str] = mapped_column(String(16))
    forecast: Mapped[str | None] = mapped_column(String(64))
    previous: Mapped[str | None] = mapped_column(String(64))
    actual: Mapped[str | None] = mapped_column(String(64))
    dedup_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PriceCache(Base):
    __tablename__ = "prices_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    ohlc_json: Mapped[list[Any]] = mapped_column(JSON)


class PostDraft(Base):
    __tablename__ = "post_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_type: Mapped[str] = mapped_column(String(16))
    source_news_ids: Mapped[list[Any] | None] = mapped_column(JSON)
    topic_tag: Mapped[str] = mapped_column(String(128), index=True)
    angle: Mapped[str] = mapped_column(Text)
    key_points: Mapped[list[Any]] = mapped_column(JSON)
    caption_draft: Mapped[str] = mapped_column(Text)
    visual_spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    dynamic_hashtags: Mapped[list[Any]] = mapped_column(JSON, default=list)
    disclaimer_required: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float)
    llm_provider: Mapped[str] = mapped_column(String(32))
    llm_model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    posts: Mapped[list[Post]] = relationship(back_populates="draft")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("post_drafts.id"))
    post_type: Mapped[str] = mapped_column(String(16))
    caption_final: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[list[Any]] = mapped_column(JSON)
    asset_path: Mapped[str] = mapped_column(Text)
    visual_type: Mapped[str] = mapped_column(String(32))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ready", index=True)
    ig_media_id: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_log: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    draft: Mapped[PostDraft | None] = relationship(back_populates="posts")


class PublishLog(Base):
    __tablename__ = "publish_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    ig_media_id: Mapped[str | None] = mapped_column(String(64))
    ig_account_pk: Mapped[str | None] = mapped_column(String(64))
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16))
    error_type: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    took_ms: Mapped[int | None] = mapped_column(Integer)


class IGAccountState(Base):
    __tablename__ = "ig_account_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    challenge_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    pause_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daily_post_count: Mapped[int] = mapped_column(Integer, default=0)
    weekly_post_count: Mapped[int] = mapped_column(Integer, default=0)
    warmup_active: Mapped[bool] = mapped_column(Boolean, default=False)
    warmup_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PostedTopic(Base):
    __tablename__ = "posted_topics"

    topic_tag: Mapped[str] = mapped_column(String(128), primary_key=True)
    last_posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReviewMessage(Base):
    """Tracks Telegram review message tied to a post for callback updates."""

    __tablename__ = "review_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id"), unique=True, index=True
    )
    chat_id: Mapped[str] = mapped_column(String(64))
    message_id: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision: Mapped[str | None] = mapped_column(String(16))


class EvergreenDraft(Base):
    __tablename__ = "evergreen_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_tag: Mapped[str] = mapped_column(String(128), index=True)
    angle: Mapped[str] = mapped_column(Text)
    key_points: Mapped[list[Any]] = mapped_column(JSON)
    caption_draft: Mapped[str] = mapped_column(Text)
    visual_spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    disclaimer_required: Mapped[bool] = mapped_column(Boolean, default=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
