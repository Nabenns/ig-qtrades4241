"""Tests for yfinance fallback price adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import pytest

from ig_qt.collector.yfinance_src import YFinanceSource


@pytest.mark.asyncio
async def test_fetch_ohlc_translates_yf_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    df = pd.DataFrame(
        {
            "Open": [1.0850, 1.0860],
            "High": [1.0870, 1.0880],
            "Low": [1.0840, 1.0850],
            "Close": [1.0865, 1.0875],
        },
        index=pd.DatetimeIndex(
            [
                datetime(2026, 5, 17, 11, tzinfo=timezone.utc),
                datetime(2026, 5, 17, 12, tzinfo=timezone.utc),
            ],
            name="Datetime",
        ),
    )
    captured: dict[str, str] = {}

    def fake_download(symbol: str, **kwargs: Any) -> pd.DataFrame:
        captured["symbol"] = symbol
        return df

    import yfinance

    monkeypatch.setattr(yfinance, "download", fake_download)

    src = YFinanceSource()
    price = await src.fetch_ohlc("EUR/USD", "1h", limit=2)
    assert captured["symbol"] == "EURUSD=X"
    assert len(price.ohlc) == 2
    assert price.ohlc[0]["close"] == 1.0865
