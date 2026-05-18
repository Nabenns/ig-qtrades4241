"""Story content builders: event reminder + market recap. Caption + visual context only."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Protocol


class _EventLike(Protocol):
    event_time: datetime
    currency: str | None
    name: str
    impact: str
    forecast: str | None
    previous: str | None


def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def build_event_reminder_context(
    *,
    events: Sequence[_EventLike],
    now: datetime,
    window_hours: int = 12,
) -> dict[str, Any]:
    end = now + timedelta(hours=window_hours)
    filtered = []
    for e in events:
        if e.impact not in ("high", "medium"):
            continue
        et = _ensure_aware(e.event_time)
        if now <= et <= end:
            filtered.append((e, et))
    items: list[dict[str, Any]] = []
    for e, et in filtered[:4]:
        local = et.astimezone(timezone(timedelta(hours=7)))  # WIB
        items.append(
            {
                "time": local.strftime("%H:%M"),
                "currency": e.currency or "—",
                "name": e.name,
                "impact": e.impact,
                "forecast": e.forecast,
                "previous": e.previous,
            }
        )
    return {
        "headline": "Event Macro Hari Ini",
        "subheadline": f"{len(items)} event high/medium impact",
        "events": items,
    }


def build_market_recap_context(
    *,
    latest_prices: Mapping[str, Sequence[dict[str, Any]]],
    symbols: Sequence[str],
) -> dict[str, Any]:
    """Build recap data: %change from previous close for each symbol."""
    recaps: list[dict[str, Any]] = []
    for sym in symbols:
        ohlc = latest_prices.get(sym, [])
        if len(ohlc) < 2:
            continue
        prev_close = float(ohlc[-2]["close"])
        last_close = float(ohlc[-1]["close"])
        change_pct = (last_close - prev_close) / prev_close * 100.0
        recaps.append(
            {
                "symbol": sym,
                "close": f"{last_close:.4f}" if last_close < 100 else f"{last_close:.2f}",
                "change_pct": change_pct,
            }
        )
    return {
        "headline": "Market Recap Harian",
        "subheadline": "Major pairs vs previous close",
        "recaps": recaps,
    }
