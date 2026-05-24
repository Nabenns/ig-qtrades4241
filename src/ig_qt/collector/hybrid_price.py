"""Hybrid price source: try primary first, fall back to secondary per symbol.

Useful when one provider has better coverage for forex pairs (e.g. TwelveData)
but lacks indices like DXY which yfinance handles natively. Avoids whole-source
failures and lets us silently fall back instead of alerting.
"""
from __future__ import annotations

from collections.abc import Sequence

from loguru import logger

from ig_qt.collector.base import NormalizedPrice, PriceSource


class HybridPriceSource:
    """Try `primary` first; on failure fall back to `secondary` for that symbol.

    Both providers must implement `fetch_ohlc(symbol, timeframe, limit)`. Only
    primary failure triggers a fallback — secondary is final.
    """

    name = "hybrid"

    def __init__(
        self,
        *,
        primary: PriceSource,
        secondary: PriceSource,
        # Symbols known to fail on primary; skip straight to secondary.
        # Saves an API call + an error log per cycle.
        skip_primary_for: Sequence[str] = (),
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._skip_primary = set(skip_primary_for)

    async def fetch_ohlc(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> NormalizedPrice:
        if symbol in self._skip_primary:
            logger.debug(
                "hybrid_price_skip_primary symbol={} → {}",
                symbol,
                self._secondary.name,
            )
            return await self._secondary.fetch_ohlc(symbol, timeframe, limit)
        try:
            return await self._primary.fetch_ohlc(symbol, timeframe, limit)
        except Exception as exc:
            logger.info(
                "hybrid_price_primary_failed source={} symbol={} err={} → {}",
                self._primary.name,
                symbol,
                str(exc)[:200],
                self._secondary.name,
            )
            return await self._secondary.fetch_ohlc(symbol, timeframe, limit)
