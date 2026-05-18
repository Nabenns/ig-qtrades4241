"""Tests for Twelve Data price adapter."""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from ig_qt.collector.twelve_data import TwelveDataSource


@pytest.mark.asyncio
async def test_fetch_ohlc_returns_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = {
        "meta": {"symbol": "EUR/USD", "interval": "1h"},
        "values": [
            {
                "datetime": "2026-05-17 12:00:00",
                "open": "1.0850",
                "high": "1.0870",
                "low": "1.0840",
                "close": "1.0865",
            },
            {
                "datetime": "2026-05-17 11:00:00",
                "open": "1.0840",
                "high": "1.0855",
                "low": "1.0830",
                "close": "1.0850",
            },
        ],
        "status": "ok",
    }

    async def fake_get(self: Any, url: str, params: Any = None, **_: Any) -> Any:
        class R:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, Any]:
                return sample

        return R()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    src = TwelveDataSource(api_key="k")
    price = await src.fetch_ohlc("EUR/USD", "1h", limit=2)
    assert price.symbol == "EUR/USD"
    assert price.timeframe == "1h"
    assert len(price.ohlc) == 2
    # Sorted oldest-first; older candle (11:00) first, newer (12:00) last
    assert price.ohlc[-1]["close"] == 1.0865
