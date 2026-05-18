"""Render technical chart PNG using mplfinance + matplotlib."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import mplfinance as mpf
import pandas as pd
from loguru import logger

_MIN_CANDLES = 50


def _to_dataframe(ohlc: Sequence[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(ohlc)
    df["t"] = pd.to_datetime(df["t"], utc=True)
    df = df.set_index("t")
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    return df.sort_index()


def render_chart_png(
    *,
    ohlc: Sequence[dict[str, Any]],
    symbol: str,
    timeframe: str,
    annotations: Sequence[str],
    headline: str,
    out_path: Path,
    size: tuple[int, int],
) -> Path:
    if len(ohlc) < _MIN_CANDLES:
        raise ValueError(
            f"too few candles for chart render: {len(ohlc)} (min {_MIN_CANDLES})"
        )
    df = _to_dataframe(ohlc)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    style = mpf.make_mpf_style(
        base_mpf_style="nightclouds",
        marketcolors=mpf.make_marketcolors(up="#26a69a", down="#ef5350", inherit=True),
        rc={"font.family": "DejaVu Sans"},
        facecolor="#0b1220",
        edgecolor="#0b1220",
        figcolor="#0b1220",
        gridcolor="#1f2937",
    )

    width_inch = size[0] / 100
    height_inch = size[1] / 100

    fig, axes = mpf.plot(
        df,
        type="candle",
        style=style,
        mav=(20, 50),
        volume=False,
        figsize=(width_inch, height_inch),
        returnfig=True,
        axisoff=False,
        update_width_config={"candle_linewidth": 0.8, "candle_width": 0.6},
    )
    main_ax = axes[0]
    main_ax.set_title(
        f"{symbol}  ·  {timeframe}",
        color="#f8fafc",
        fontsize=22,
        loc="left",
        pad=18,
    )
    main_ax.text(
        0.99,
        1.02,
        headline,
        transform=main_ax.transAxes,
        color="#94a3b8",
        ha="right",
        va="bottom",
        fontsize=18,
    )
    for ann in annotations[:4]:
        first_token = ann.split()[0] if ann.split() else ""
        try:
            level = float(first_token)
        except ValueError:
            continue
        main_ax.axhline(level, color="#ffb020", linewidth=1.2, alpha=0.7, linestyle="--")
        main_ax.text(
            df.index[-1],
            level,
            f"  {ann}",
            color="#ffb020",
            fontsize=14,
            va="center",
        )

    fig.savefig(
        out_path,
        dpi=100,
        facecolor="#0b1220",
        format="png",
    )
    logger.info("chart_render_done symbol={} out={}", symbol, out_path)
    return out_path
