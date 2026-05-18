"""Source Protocol + normalized item shapes."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalize_text(s: str) -> str:
    return _NON_ALNUM.sub("", s.lower().strip())


def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:32]  # noqa: S324 (not crypto)


@dataclass(frozen=True, slots=True)
class NormalizedNews:
    source: str
    external_id: str | None
    published_at: datetime | None
    title: str
    summary: str | None
    url: str
    keywords: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def dedup_key(self) -> str:
        date_part = (
            self.published_at.date().isoformat() if self.published_at else "no-date"
        )
        return _hash(f"news|{date_part}|{_normalize_text(self.title)}")


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    source: str
    event_time: datetime
    country: str | None
    currency: str | None
    name: str
    impact: str
    forecast: str | None
    previous: str | None
    actual: str | None

    def dedup_key(self) -> str:
        return _hash(
            f"event|{self.event_time.isoformat()}|{(self.currency or '').upper()}|"
            f"{_normalize_text(self.name)}"
        )


@dataclass(frozen=True, slots=True)
class NormalizedPrice:
    symbol: str
    timeframe: str
    fetched_at: datetime
    ohlc: list[dict[str, Any]]


@runtime_checkable
class Source(Protocol):
    name: str

    async def fetch_news(self) -> Sequence[NormalizedNews]: ...


@runtime_checkable
class CalendarSource(Protocol):
    name: str

    async def fetch_events(self) -> Sequence[NormalizedEvent]: ...


@runtime_checkable
class PriceSource(Protocol):
    name: str

    async def fetch_ohlc(self, symbol: str, timeframe: str, limit: int) -> NormalizedPrice: ...
