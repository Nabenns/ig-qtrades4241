"""Twelve Data prices adapter (free tier)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from dateutil import parser as dtparser
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.collector.base import NormalizedPrice

_BASE = "https://api.twelvedata.com/time_series"


class TwelveDataSource:
    name = "twelve_data"

    def __init__(self, *, api_key: str, timeout: float = 20.0) -> None:
        self._api_key = api_key
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(_BASE, params=params)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data

    async def fetch_ohlc(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> NormalizedPrice:
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": timeframe,
            "outputsize": limit,
            "apikey": self._api_key,
            "format": "JSON",
        }
        data = await self._get(params)
        if data.get("status") == "error":
            raise RuntimeError(f"twelvedata error: {data.get('message')}")
        ohlc: list[dict[str, Any]] = []
        for v in data.get("values", []):
            try:
                dt = dtparser.parse(v["datetime"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                ohlc.append(
                    {
                        "t": dt.isoformat(),
                        "open": float(v["open"]),
                        "high": float(v["high"]),
                        "low": float(v["low"]),
                        "close": float(v["close"]),
                    }
                )
            except (KeyError, ValueError) as exc:
                logger.warning("twelvedata_skip_bad_row error={} row={}", exc, v)
        ohlc.sort(key=lambda x: x["t"])
        return NormalizedPrice(
            symbol=symbol,
            timeframe=timeframe,
            fetched_at=datetime.now(UTC),
            ohlc=ohlc,
        )
