"""Collector orchestration: run all enabled sources, insert with dedup."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from loguru import logger
from sqlalchemy import Engine

from ig_qt.collector.base import NormalizedEvent, NormalizedNews
from ig_qt.collector.dedup import insert_events_dedup, insert_news_dedup
from ig_qt.config import AppConfig
from ig_qt.db import session_scope


@runtime_checkable
class _NewsSource(Protocol):
    name: str

    async def fetch_news(self) -> Sequence[NormalizedNews]: ...


@runtime_checkable
class _CalSource(Protocol):
    name: str

    async def fetch_events(self) -> Sequence[NormalizedEvent]: ...


@dataclass(frozen=True, slots=True)
class CollectResult:
    news_inserted: int
    events_inserted: int
    failed_sources: list[str] = field(default_factory=list)


class CollectorPipeline:
    def __init__(
        self,
        *,
        engine: Engine,
        news_sources: Sequence[_NewsSource],
        calendar_sources: Sequence[_CalSource],
    ) -> None:
        self._engine = engine
        self._news_sources = list(news_sources)
        self._calendar_sources = list(calendar_sources)

    async def run_once(self) -> CollectResult:
        all_news: list[NormalizedNews] = []
        all_events: list[NormalizedEvent] = []
        failed: list[str] = []

        for src in self._news_sources:
            try:
                items = await src.fetch_news()
                all_news.extend(items)
            except Exception as exc:
                logger.warning("source_failed name={} error={}", src.name, exc)
                failed.append(src.name)

        for cal_src in self._calendar_sources:
            try:
                cal_items = await cal_src.fetch_events()
                all_events.extend(cal_items)
            except Exception as exc:
                logger.warning("source_failed name={} error={}", cal_src.name, exc)
                failed.append(cal_src.name)

        with session_scope(self._engine) as s:
            news_n = insert_news_dedup(s, all_news)
            events_n = insert_events_dedup(s, all_events)

        result = CollectResult(
            news_inserted=news_n, events_inserted=events_n, failed_sources=failed
        )
        logger.info(
            "collector_run_done news={} events={} failed={}",
            result.news_inserted,
            result.events_inserted,
            result.failed_sources,
        )
        return result


def build_pipeline_from_config(engine: Engine, cfg: AppConfig) -> CollectorPipeline:
    """Build pipeline using AppConfig.collector flags."""
    from ig_qt.collector.forex_factory import ForexFactorySource
    from ig_qt.collector.gnews import GNewsSource
    from ig_qt.collector.news_api import NewsAPISource
    from ig_qt.collector.rss import RSSSource

    news_sources: list[_NewsSource] = []
    if cfg.collector.news_api_enabled and cfg.collector.news_api_key:
        news_sources.append(
            NewsAPISource(api_key=cfg.collector.news_api_key.get_secret_value())
        )
    if cfg.collector.gnews_enabled and cfg.collector.gnews_key:
        news_sources.append(
            GNewsSource(api_key=cfg.collector.gnews_key.get_secret_value())
        )
    if cfg.collector.rss_enabled:
        news_sources.append(RSSSource())

    cal_sources: list[_CalSource] = []
    if cfg.collector.forex_factory_enabled:
        cal_sources.append(ForexFactorySource(timezone_id=cfg.schedule.timezone))

    return CollectorPipeline(
        engine=engine, news_sources=news_sources, calendar_sources=cal_sources
    )
