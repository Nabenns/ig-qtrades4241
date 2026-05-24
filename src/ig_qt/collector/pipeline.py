"""Collector orchestration: run all enabled sources, insert with dedup."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from loguru import logger
from sqlalchemy import Engine

from ig_qt.collector.base import NormalizedEvent, NormalizedNews, NormalizedPrice
from ig_qt.collector.dedup import (
    insert_events_dedup,
    insert_news_dedup,
    upsert_price_cache,
)
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


@runtime_checkable
class _PriceSource(Protocol):
    name: str

    async def fetch_ohlc(self, symbol: str, timeframe: str, limit: int) -> NormalizedPrice: ...


@dataclass(frozen=True, slots=True)
class CollectResult:
    news_inserted: int
    events_inserted: int
    prices_cached: int = 0
    failed_sources: list[str] = field(default_factory=list)


class CollectorPipeline:
    def __init__(
        self,
        *,
        engine: Engine,
        news_sources: Sequence[_NewsSource],
        calendar_sources: Sequence[_CalSource],
        price_source: _PriceSource | None = None,
        price_symbols: Sequence[str] = (),
        price_timeframe: str = "1h",
    ) -> None:
        self._engine = engine
        self._news_sources = list(news_sources)
        self._calendar_sources = list(calendar_sources)
        self._price_source = price_source
        self._price_symbols = list(price_symbols)
        self._price_timeframe = price_timeframe

    async def _fetch_prices(self) -> tuple[list[NormalizedPrice], list[str]]:
        """Fetch OHLC for each configured symbol via the active price source.
        Returns (prices, failed_symbols). Continues on per-symbol errors so a
        single bad symbol doesn't kill the whole price snapshot.
        """
        if self._price_source is None or not self._price_symbols:
            return [], []
        prices: list[NormalizedPrice] = []
        failed: list[str] = []

        async def _one(sym: str) -> None:
            assert self._price_source is not None  # nosec  (narrowed above)
            try:
                p = await self._price_source.fetch_ohlc(sym, self._price_timeframe, 200)
                if p.ohlc:
                    prices.append(p)
                else:
                    logger.warning("price_empty source={} symbol={}", self._price_source.name, sym)
            except Exception as exc:
                logger.warning(
                    "price_fetch_failed source={} symbol={} err={}",
                    self._price_source.name,
                    sym,
                    exc,
                )
                failed.append(f"{self._price_source.name}:{sym}")

        await asyncio.gather(*(_one(s) for s in self._price_symbols))
        return prices, failed

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

        prices, price_failed = await self._fetch_prices()
        failed.extend(price_failed)

        with session_scope(self._engine) as s:
            news_n = insert_news_dedup(s, all_news)
            events_n = insert_events_dedup(s, all_events)
            prices_n = upsert_price_cache(s, prices)

        result = CollectResult(
            news_inserted=news_n,
            events_inserted=events_n,
            prices_cached=prices_n,
            failed_sources=failed,
        )
        logger.info(
            "collector_run_done news={} events={} prices={} failed={}",
            result.news_inserted,
            result.events_inserted,
            result.prices_cached,
            result.failed_sources,
        )
        return result


def build_pipeline_from_config(engine: Engine, cfg: AppConfig) -> CollectorPipeline:
    """Build pipeline using AppConfig.collector flags."""
    from ig_qt.collector.forex_factory import ForexFactorySource
    from ig_qt.collector.gnews import GNewsSource
    from ig_qt.collector.news_api import NewsAPISource
    from ig_qt.collector.rss import RSSSource
    from ig_qt.collector.twelve_data import TwelveDataSource
    from ig_qt.collector.yfinance_src import YFinanceSource

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

    # Price source: prefer TwelveData when key is provided & valid; else yfinance.
    # When TD is active we wrap it in a hybrid source so symbols TD doesn't
    # support (e.g. DXY index) silently fall back to yfinance.
    price_source: _PriceSource | None = None
    yf_source = YFinanceSource()
    if cfg.collector.twelve_data_enabled and cfg.collector.twelve_data_key:
        from ig_qt.collector.hybrid_price import HybridPriceSource

        td_source = TwelveDataSource(
            api_key=cfg.collector.twelve_data_key.get_secret_value()
        )
        price_source = HybridPriceSource(
            primary=td_source,
            secondary=yf_source,
            skip_primary_for=("DXY",),  # TD has no native DXY index
        )
    else:
        price_source = yf_source

    return CollectorPipeline(
        engine=engine,
        news_sources=news_sources,
        calendar_sources=cal_sources,
        price_source=price_source,
        price_symbols=cfg.collector.symbols,
        price_timeframe="1h",
    )
