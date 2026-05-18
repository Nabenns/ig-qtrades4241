"""yfinance fallback price source. Run blocking yfinance call in thread."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import yfinance as yf
from loguru import logger

from ig_qt.collector.base import NormalizedPrice

_SYMBOL_MAP = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "USD/CAD": "USDCAD=X",
    "AUD/USD": "AUDUSD=X",
    "XAU/USD": "GC=F",
    "DXY": "DX-Y.NYB",
    "BTC/USD": "BTC-USD",
}

_INTERVAL_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "1h", "1d": "1d"}


class YFinanceSource:
    name = "yfinance"

    async def fetch_ohlc(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> NormalizedPrice:
        yf_symbol = _SYMBOL_MAP.get(symbol, symbol)
        yf_interval = _INTERVAL_MAP.get(timeframe, "1h")

        def _download() -> Any:
            period = "60d" if yf_interval == "1d" else "30d"
            return yf.download(
                yf_symbol,
                period=period,
                interval=yf_interval,
                progress=False,
                auto_adjust=False,
            )

        df = await asyncio.to_thread(_download)
        if df is None or len(df) == 0:
            logger.warning("yfinance_empty symbol={} yf_symbol={}", symbol, yf_symbol)
            return NormalizedPrice(
                symbol=symbol,
                timeframe=timeframe,
                fetched_at=datetime.now(UTC),
                ohlc=[],
            )
        df = df.tail(limit)
        ohlc: list[dict[str, Any]] = []
        for ts, row in df.iterrows():
            dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            ohlc.append(
                {
                    "t": dt.isoformat(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                }
            )
        return NormalizedPrice(
            symbol=symbol,
            timeframe=timeframe,
            fetched_at=datetime.now(UTC),
            ohlc=ohlc,
        )
