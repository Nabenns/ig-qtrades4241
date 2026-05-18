"""Tests for chart renderer."""
from __future__ import annotations

import math
from pathlib import Path

import pytest
from PIL import Image

from ig_qt.composer.chart_renderer import render_chart_png


def _ohlc_fixture(n: int = 100) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    base = 1.0850
    for i in range(n):
        v = base + math.sin(i / 5) * 0.005
        rows.append(
            {
                "t": f"2026-05-{1 + i // 24:02d}T{i % 24:02d}:00:00+00:00",
                "open": v,
                "high": v + 0.0015,
                "low": v - 0.0015,
                "close": v + 0.0005,
            }
        )
    return rows


def test_render_chart_produces_png(tmp_path: Path) -> None:
    out = tmp_path / "chart.png"
    render_chart_png(
        ohlc=_ohlc_fixture(),
        symbol="EUR/USD",
        timeframe="1h",
        annotations=["1.0850 support", "1.0870 resistance"],
        headline="EUR/USD at key level",
        out_path=out,
        size=(1080, 1080),
    )
    assert out.exists()
    img = Image.open(out)
    assert img.size[0] >= 1000


def test_render_chart_raises_when_too_few_candles(tmp_path: Path) -> None:
    out = tmp_path / "chart.png"
    with pytest.raises(ValueError, match="too few candles"):
        render_chart_png(
            ohlc=_ohlc_fixture(10),
            symbol="EUR/USD",
            timeframe="1h",
            annotations=[],
            headline="x",
            out_path=out,
            size=(1080, 1080),
        )
