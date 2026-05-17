# M2 Collector — Implementation Plan

> **Parent:** [`../2026-05-17-ig-forex-automation.md`](../2026-05-17-ig-forex-automation.md)
> **Prereq:** M1 complete.

**Goal:** Implement source adapters for news (NewsAPI, GNews), prices (Twelve Data + yfinance fallback), and economic calendar (Forex Factory via Playwright). All sources normalize to common schemas, dedup is centralized, pipeline orchestrator runs sources with per-source try/except so one failure doesn't block others. End state: `python -m ig_qt collect --once` fetches from all enabled sources and inserts into SQLite.

**Files created in M2:**
- `src/ig_qt/collector/__init__.py`, `base.py`, `pipeline.py`
- `src/ig_qt/collector/news_api.py`, `gnews.py`, `twelve_data.py`, `yfinance_src.py`, `forex_factory.py`
- `src/ig_qt/collector/playwright_runner.py`
- `src/ig_qt/collector/dedup.py`
- `tests/collector/test_*.py` (one per module)
- Modify: `pyproject.toml` (add deps), `src/ig_qt/__main__.py` (add `collect` command)

**New dependencies:** `playwright>=1.47`, `beautifulsoup4>=4.12`, `yfinance>=0.2.40`, `python-dateutil>=2.9`.

---

## Task 2.1: Add collector dependencies + scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ig_qt/collector/__init__.py`
- Create: `src/ig_qt/collector/base.py`
- Create: `tests/collector/__init__.py`
- Create: `tests/collector/test_base.py`

- [ ] **Step 1: Add deps to `pyproject.toml`**

In `[project] dependencies`, append:

```toml
    "playwright>=1.47",
    "beautifulsoup4>=4.12",
    "yfinance>=0.2.40",
    "python-dateutil>=2.9",
```

- [ ] **Step 2: Sync**

```bash
uv sync
uv run playwright install chromium
```

Expected: chromium binary downloaded to user cache.

- [ ] **Step 3: Write failing test**

`tests/collector/test_base.py`:

```python
"""Tests for collector base types."""
from __future__ import annotations

from datetime import datetime, timezone

from ig_qt.collector.base import NormalizedNews, NormalizedEvent


def test_normalized_news_dedup_key_stable() -> None:
    n1 = NormalizedNews(
        source="newsapi",
        external_id="x",
        published_at=datetime(2026, 5, 17, 12, tzinfo=timezone.utc),
        title="Fed Holds Rates",
        summary=None,
        url="https://x",
        keywords=["fed", "rates"],
        raw_payload={"a": 1},
    )
    n2 = NormalizedNews(
        source="gnews",
        external_id="y",
        published_at=datetime(2026, 5, 17, 18, tzinfo=timezone.utc),
        title="  fed holds rates ",  # whitespace + case
        summary="diff",
        url="https://y",
        keywords=[],
        raw_payload={},
    )
    # Same normalized title + same date → same dedup key
    assert n1.dedup_key() == n2.dedup_key()


def test_normalized_event_dedup_key_includes_currency_and_time() -> None:
    e1 = NormalizedEvent(
        source="forex_factory",
        event_time=datetime(2026, 5, 17, 12, 30, tzinfo=timezone.utc),
        country="US",
        currency="USD",
        name="CPI m/m",
        impact="high",
        forecast="0.3%",
        previous="0.4%",
        actual=None,
    )
    assert "USD" in e1.dedup_key()
    assert "cpi" in e1.dedup_key()
```

- [ ] **Step 4: Run test (should fail)**

```bash
uv run pytest tests/collector/test_base.py -v
```

Expected: FAIL.

- [ ] **Step 5: Implement `src/ig_qt/collector/__init__.py`**

```python
"""Data collection adapters."""
from __future__ import annotations

from ig_qt.collector.base import NormalizedEvent, NormalizedNews, NormalizedPrice, Source

__all__ = ["NormalizedEvent", "NormalizedNews", "NormalizedPrice", "Source"]
```

- [ ] **Step 6: Implement `src/ig_qt/collector/base.py`**

```python
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
    impact: str  # low | medium | high
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
```

- [ ] **Step 7: Run test (should pass)**

```bash
uv run pytest tests/collector/test_base.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock src/ig_qt/collector/ tests/collector/__init__.py tests/collector/test_base.py
git commit -m "feat(collector): add base types and source protocols"
```

---

## Task 2.2: Dedup helper + unit tests

**Files:**
- Create: `src/ig_qt/collector/dedup.py`
- Create: `tests/collector/test_dedup.py`

- [ ] **Step 1: Write failing test**

`tests/collector/test_dedup.py`:

```python
"""Tests for dedup helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ig_qt.collector.base import NormalizedEvent, NormalizedNews
from ig_qt.collector.dedup import insert_events_dedup, insert_news_dedup
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Event, RawNews
from sqlalchemy import select


def test_insert_news_dedup_skips_duplicates(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)

    n1 = NormalizedNews(
        source="newsapi",
        external_id="1",
        published_at=datetime(2026, 5, 17, tzinfo=timezone.utc),
        title="Fed Holds Rates",
        summary=None,
        url="https://x",
        keywords=[],
        raw_payload={},
    )
    n2 = NormalizedNews(
        source="gnews",
        external_id="2",
        published_at=datetime(2026, 5, 17, 12, tzinfo=timezone.utc),
        title="fed holds rates",  # same dedup key
        summary=None,
        url="https://y",
        keywords=[],
        raw_payload={},
    )

    with session_scope(engine) as s:
        inserted = insert_news_dedup(s, [n1, n2])
    assert inserted == 1

    with session_scope(engine) as s:
        rows = s.execute(select(RawNews)).scalars().all()
    assert len(rows) == 1


def test_insert_events_dedup(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)

    e1 = NormalizedEvent(
        source="ff",
        event_time=datetime(2026, 5, 17, 12, 30, tzinfo=timezone.utc),
        country="US",
        currency="USD",
        name="CPI m/m",
        impact="high",
        forecast="0.3%",
        previous="0.4%",
        actual=None,
    )
    with session_scope(engine) as s:
        inserted = insert_events_dedup(s, [e1, e1])
    assert inserted == 1

    with session_scope(engine) as s:
        rows = s.execute(select(Event)).scalars().all()
    assert len(rows) == 1
```

- [ ] **Step 2: Run test (should fail)**

```bash
uv run pytest tests/collector/test_dedup.py -v
```

- [ ] **Step 3: Implement `src/ig_qt/collector/dedup.py`**

```python
"""Insert helpers with INSERT OR IGNORE semantics via dedup_key."""
from __future__ import annotations

from collections.abc import Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from ig_qt.collector.base import NormalizedEvent, NormalizedNews
from ig_qt.models import Event, RawNews


def insert_news_dedup(session: Session, items: Sequence[NormalizedNews]) -> int:
    """Insert news items, skipping duplicates by dedup_key. Returns count inserted."""
    if not items:
        return 0
    keys = {it.dedup_key() for it in items}
    existing = set(
        session.execute(
            select(RawNews.dedup_key).where(RawNews.dedup_key.in_(keys))
        ).scalars()
    )
    inserted = 0
    seen_in_batch: set[str] = set()
    for it in items:
        k = it.dedup_key()
        if k in existing or k in seen_in_batch:
            continue
        seen_in_batch.add(k)
        session.add(
            RawNews(
                source=it.source,
                external_id=it.external_id,
                published_at=it.published_at,
                title=it.title,
                summary=it.summary,
                url=it.url,
                keywords=list(it.keywords),
                raw_payload=dict(it.raw_payload),
                dedup_key=k,
            )
        )
        inserted += 1
    logger.info("insert_news_dedup inserted={} skipped={}", inserted, len(items) - inserted)
    return inserted


def insert_events_dedup(session: Session, items: Sequence[NormalizedEvent]) -> int:
    if not items:
        return 0
    keys = {it.dedup_key() for it in items}
    existing = set(
        session.execute(select(Event.dedup_key).where(Event.dedup_key.in_(keys))).scalars()
    )
    inserted = 0
    seen_in_batch: set[str] = set()
    for it in items:
        k = it.dedup_key()
        if k in existing or k in seen_in_batch:
            continue
        seen_in_batch.add(k)
        session.add(
            Event(
                source=it.source,
                event_time=it.event_time,
                country=it.country,
                currency=it.currency,
                name=it.name,
                impact=it.impact,
                forecast=it.forecast,
                previous=it.previous,
                actual=it.actual,
                dedup_key=k,
            )
        )
        inserted += 1
    logger.info("insert_events_dedup inserted={} skipped={}", inserted, len(items) - inserted)
    return inserted
```

- [ ] **Step 4: Run + mypy + commit**

```bash
uv run pytest tests/collector/test_dedup.py -v
uv run mypy --strict src/ig_qt/collector/
git add src/ig_qt/collector/dedup.py tests/collector/test_dedup.py
git commit -m "feat(collector): add dedup insert helpers"
```

---

## Task 2.3: NewsAPI adapter

**Files:**
- Create: `src/ig_qt/collector/news_api.py`
- Create: `tests/collector/test_news_api.py`

- [ ] **Step 1: Write failing test**

`tests/collector/test_news_api.py`:

```python
"""Tests for NewsAPI adapter."""
from __future__ import annotations

import httpx
import pytest

from ig_qt.collector.news_api import NewsAPISource


@pytest.mark.asyncio
async def test_news_api_fetches_and_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = {
        "status": "ok",
        "articles": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "title": "Fed Holds Rates Steady",
                "description": "FOMC kept...",
                "url": "https://example.com/a",
                "publishedAt": "2026-05-17T12:00:00Z",
                "content": "Long content",
            },
            {
                "source": {"name": "Bloomberg"},
                "title": "ECB Signals Cut",
                "description": None,
                "url": "https://example.com/b",
                "publishedAt": "2026-05-17T13:00:00Z",
                "content": None,
            },
        ],
    }

    async def fake_get(self, url, params=None, **_):  # type: ignore[no-untyped-def]
        class R:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):  # type: ignore[no-untyped-def]
                return sample

        return R()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    src = NewsAPISource(api_key="k", keywords=["forex", "fed"])
    items = await src.fetch_news()
    assert len(items) == 2
    assert items[0].title == "Fed Holds Rates Steady"
    assert items[0].source == "newsapi"
    assert items[0].published_at is not None
```

- [ ] **Step 2: Implement `src/ig_qt/collector/news_api.py`**

```python
"""NewsAPI.org adapter."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

import httpx
from dateutil import parser as dtparser
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.collector.base import NormalizedNews

_BASE = "https://newsapi.org/v2/everything"


class NewsAPISource:
    name = "newsapi"

    def __init__(
        self,
        *,
        api_key: str,
        keywords: Sequence[str] | None = None,
        page_size: int = 50,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._keywords = list(keywords) if keywords else ["forex", "fed", "ecb", "boe", "boj"]
        self._page_size = page_size
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _get(self) -> dict[str, Any]:
        query = " OR ".join(self._keywords)
        params: dict[str, Any] = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": self._page_size,
            "apiKey": self._api_key,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(_BASE, params=params)
            resp.raise_for_status()
            return resp.json()

    async def fetch_news(self) -> Sequence[NormalizedNews]:
        try:
            data = await self._get()
        except Exception as exc:
            logger.warning("newsapi_fetch_failed error={}", exc)
            return []
        if data.get("status") != "ok":
            logger.warning("newsapi_status_not_ok body={}", data)
            return []
        items: list[NormalizedNews] = []
        for art in data.get("articles", []):
            title = (art.get("title") or "").strip()
            if not title or title == "[Removed]":
                continue
            published = art.get("publishedAt")
            published_dt: datetime | None = None
            if published:
                try:
                    parsed = dtparser.isoparse(published)
                    published_dt = (
                        parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                    )
                except (ValueError, TypeError):
                    published_dt = None
            url = art.get("url") or ""
            items.append(
                NormalizedNews(
                    source=self.name,
                    external_id=url or None,
                    published_at=published_dt,
                    title=title,
                    summary=art.get("description"),
                    url=url,
                    keywords=list(self._keywords),
                    raw_payload=art,
                )
            )
        logger.info("newsapi_fetched count={}", len(items))
        return items
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/collector/test_news_api.py -v
uv run mypy --strict src/ig_qt/collector/news_api.py
git add src/ig_qt/collector/news_api.py tests/collector/test_news_api.py
git commit -m "feat(collector): add NewsAPI source adapter"
```

---

## Task 2.4: GNews adapter

**Files:**
- Create: `src/ig_qt/collector/gnews.py`
- Create: `tests/collector/test_gnews.py`

- [ ] **Step 1: Write failing test**

`tests/collector/test_gnews.py`:

```python
"""Tests for GNews adapter."""
from __future__ import annotations

import httpx
import pytest

from ig_qt.collector.gnews import GNewsSource


@pytest.mark.asyncio
async def test_gnews_fetches_and_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = {
        "totalArticles": 2,
        "articles": [
            {
                "title": "USD Strengthens After CPI",
                "description": "...",
                "content": "...",
                "url": "https://x.example/1",
                "image": "https://x.example/img.jpg",
                "publishedAt": "2026-05-17T12:00:00Z",
                "source": {"name": "Reuters", "url": "https://reuters.com"},
            },
            {
                "title": "Gold Hits New High",
                "description": "...",
                "content": "...",
                "url": "https://x.example/2",
                "image": None,
                "publishedAt": "2026-05-17T11:00:00Z",
                "source": {"name": "Bloomberg", "url": "https://bloomberg.com"},
            },
        ],
    }

    async def fake_get(self, url, params=None, **_):  # type: ignore[no-untyped-def]
        class R:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):  # type: ignore[no-untyped-def]
                return sample

        return R()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    src = GNewsSource(api_key="k", keywords=["forex"])
    items = await src.fetch_news()
    assert len(items) == 2
    assert items[0].source == "gnews"
    assert items[0].title.startswith("USD")
```

- [ ] **Step 2: Implement `src/ig_qt/collector/gnews.py`**

```python
"""GNews adapter (https://gnews.io)."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

import httpx
from dateutil import parser as dtparser
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.collector.base import NormalizedNews

_BASE = "https://gnews.io/api/v4/search"


class GNewsSource:
    name = "gnews"

    def __init__(
        self,
        *,
        api_key: str,
        keywords: Sequence[str] | None = None,
        max_results: int = 25,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._keywords = list(keywords) if keywords else ["forex", "currency", "fed", "ecb"]
        self._max_results = max_results
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _get(self) -> dict[str, Any]:
        query = " OR ".join(self._keywords)
        params: dict[str, Any] = {
            "q": query,
            "lang": "en",
            "max": self._max_results,
            "sortby": "publishedAt",
            "apikey": self._api_key,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(_BASE, params=params)
            resp.raise_for_status()
            return resp.json()

    async def fetch_news(self) -> Sequence[NormalizedNews]:
        try:
            data = await self._get()
        except Exception as exc:
            logger.warning("gnews_fetch_failed error={}", exc)
            return []
        items: list[NormalizedNews] = []
        for art in data.get("articles", []):
            title = (art.get("title") or "").strip()
            if not title:
                continue
            published = art.get("publishedAt")
            published_dt: datetime | None = None
            if published:
                try:
                    parsed = dtparser.isoparse(published)
                    published_dt = (
                        parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
                    )
                except (ValueError, TypeError):
                    published_dt = None
            url = art.get("url") or ""
            items.append(
                NormalizedNews(
                    source=self.name,
                    external_id=url or None,
                    published_at=published_dt,
                    title=title,
                    summary=art.get("description"),
                    url=url,
                    keywords=list(self._keywords),
                    raw_payload=art,
                )
            )
        logger.info("gnews_fetched count={}", len(items))
        return items
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/collector/test_gnews.py -v
uv run mypy --strict src/ig_qt/collector/gnews.py
git add src/ig_qt/collector/gnews.py tests/collector/test_gnews.py
git commit -m "feat(collector): add GNews source adapter"
```

---

## Task 2.5: Twelve Data price adapter

**Files:**
- Create: `src/ig_qt/collector/twelve_data.py`
- Create: `tests/collector/test_twelve_data.py`

- [ ] **Step 1: Write failing test**

`tests/collector/test_twelve_data.py`:

```python
"""Tests for Twelve Data price adapter."""
from __future__ import annotations

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

    async def fake_get(self, url, params=None, **_):  # type: ignore[no-untyped-def]
        class R:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):  # type: ignore[no-untyped-def]
                return sample

        return R()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    src = TwelveDataSource(api_key="k")
    price = await src.fetch_ohlc("EUR/USD", "1h", limit=2)
    assert price.symbol == "EUR/USD"
    assert price.timeframe == "1h"
    assert len(price.ohlc) == 2
    assert price.ohlc[0]["close"] == 1.0865
```

- [ ] **Step 2: Implement `src/ig_qt/collector/twelve_data.py`**

```python
"""Twelve Data prices adapter (free tier)."""
from __future__ import annotations

from datetime import datetime, timezone
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
            return resp.json()

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
                    dt = dt.replace(tzinfo=timezone.utc)
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
        # Twelve Data returns newest-first; sort oldest-first for charting.
        ohlc.sort(key=lambda x: x["t"])
        return NormalizedPrice(
            symbol=symbol,
            timeframe=timeframe,
            fetched_at=datetime.now(timezone.utc),
            ohlc=ohlc,
        )
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/collector/test_twelve_data.py -v
uv run mypy --strict src/ig_qt/collector/twelve_data.py
git add src/ig_qt/collector/twelve_data.py tests/collector/test_twelve_data.py
git commit -m "feat(collector): add Twelve Data price adapter"
```

---

## Task 2.6: yfinance fallback adapter

**Files:**
- Create: `src/ig_qt/collector/yfinance_src.py`
- Create: `tests/collector/test_yfinance_src.py`

- [ ] **Step 1: Write failing test**

`tests/collector/test_yfinance_src.py`:

```python
"""Tests for yfinance fallback price adapter."""
from __future__ import annotations

from datetime import datetime, timezone

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
            [datetime(2026, 5, 17, 11, tzinfo=timezone.utc),
             datetime(2026, 5, 17, 12, tzinfo=timezone.utc)],
            name="Datetime",
        ),
    )
    captured: dict[str, str] = {}

    def fake_download(symbol: str, **kwargs):  # type: ignore[no-untyped-def]
        captured["symbol"] = symbol
        return df

    import yfinance

    monkeypatch.setattr(yfinance, "download", fake_download)

    src = YFinanceSource()
    price = await src.fetch_ohlc("EUR/USD", "1h", limit=2)
    assert captured["symbol"] == "EURUSD=X"
    assert len(price.ohlc) == 2
    assert price.ohlc[0]["close"] == 1.0865
```

- [ ] **Step 2: Implement `src/ig_qt/collector/yfinance_src.py`**

```python
"""yfinance fallback price source. Run blocking yfinance call in thread."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import yfinance as yf
from loguru import logger

from ig_qt.collector.base import NormalizedPrice

# Map common forex pair to yfinance ticker convention.
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
            # Period heuristic: long enough to satisfy `limit` for the interval.
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
                fetched_at=datetime.now(timezone.utc),
                ohlc=[],
            )
        df = df.tail(limit)
        ohlc: list[dict[str, Any]] = []
        for ts, row in df.iterrows():
            dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
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
            fetched_at=datetime.now(timezone.utc),
            ohlc=ohlc,
        )
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/collector/test_yfinance_src.py -v
uv run mypy --strict src/ig_qt/collector/yfinance_src.py
git add src/ig_qt/collector/yfinance_src.py tests/collector/test_yfinance_src.py
git commit -m "feat(collector): add yfinance fallback price adapter"
```

---

## Task 2.7: Playwright runner helper

**Files:**
- Create: `src/ig_qt/collector/playwright_runner.py`
- Create: `tests/collector/test_playwright_runner.py`

- [ ] **Step 1: Write failing test**

`tests/collector/test_playwright_runner.py`:

```python
"""Tests for Playwright runner helpers."""
from __future__ import annotations

from ig_qt.collector.playwright_runner import pick_user_agent


def test_pick_user_agent_returns_one_of_pool() -> None:
    ua = pick_user_agent()
    assert "Mozilla" in ua
    assert any(name in ua for name in ("Chrome", "Safari", "Firefox"))


def test_pick_user_agent_with_seed_is_deterministic() -> None:
    a = pick_user_agent(seed=1)
    b = pick_user_agent(seed=1)
    assert a == b
```

- [ ] **Step 2: Implement `src/ig_qt/collector/playwright_runner.py`**

```python
"""Shared Playwright session helper."""
from __future__ import annotations

import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from loguru import logger
from playwright.async_api import BrowserContext, async_playwright

_UA_POOL: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
)


def pick_user_agent(*, seed: int | None = None) -> str:
    rng = random.Random(seed) if seed is not None else random
    return rng.choice(_UA_POOL)


@asynccontextmanager
async def browser_session(
    *, timezone_id: str = "Asia/Jakarta", locale: str = "en-US"
) -> AsyncIterator[BrowserContext]:
    """Yield a Playwright context with realistic UA + timezone. Always closes browser."""
    ua = pick_user_agent()
    logger.debug("playwright_launch ua={}", ua)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=ua,
            timezone_id=timezone_id,
            locale=locale,
            viewport={"width": 1366, "height": 768},
        )
        try:
            yield ctx
        finally:
            await ctx.close()
            await browser.close()
            logger.debug("playwright_closed")
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/collector/test_playwright_runner.py -v
uv run mypy --strict src/ig_qt/collector/playwright_runner.py
git add src/ig_qt/collector/playwright_runner.py tests/collector/test_playwright_runner.py
git commit -m "feat(collector): add shared Playwright session helper"
```

---

## Task 2.8: Forex Factory calendar scraper

**Files:**
- Create: `src/ig_qt/collector/forex_factory.py`
- Create: `tests/collector/test_forex_factory.py`
- Create: `tests/collector/fixtures/ff_sample.html`

- [ ] **Step 1: Capture a Forex Factory sample HTML for testing**

Save a representative snippet to `tests/collector/fixtures/ff_sample.html`. Use this minimal fixture (real selectors may evolve; runner reads via Playwright in production):

```html
<!doctype html><html><body>
<table class="calendar__table">
  <tr class="calendar__row" data-event-id="100">
    <td class="calendar__date">May 17</td>
    <td class="calendar__time">12:30pm</td>
    <td class="calendar__currency">USD</td>
    <td class="calendar__impact"><span class="impact impact--high"></span></td>
    <td class="calendar__event">CPI m/m</td>
    <td class="calendar__forecast">0.3%</td>
    <td class="calendar__previous">0.4%</td>
    <td class="calendar__actual"></td>
  </tr>
  <tr class="calendar__row" data-event-id="101">
    <td class="calendar__date"></td>
    <td class="calendar__time">2:00pm</td>
    <td class="calendar__currency">EUR</td>
    <td class="calendar__impact"><span class="impact impact--medium"></span></td>
    <td class="calendar__event">ECB Press Conference</td>
    <td class="calendar__forecast"></td>
    <td class="calendar__previous"></td>
    <td class="calendar__actual"></td>
  </tr>
</table>
</body></html>
```

- [ ] **Step 2: Write failing test**

`tests/collector/test_forex_factory.py`:

```python
"""Tests for Forex Factory parser."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ig_qt.collector.forex_factory import parse_forex_factory_html


def test_parse_extracts_two_events() -> None:
    fixture = Path(__file__).parent / "fixtures" / "ff_sample.html"
    html = fixture.read_text(encoding="utf-8")
    base_date = datetime(2026, 5, 17, tzinfo=timezone.utc)
    events = parse_forex_factory_html(html, fallback_date=base_date)
    assert len(events) == 2
    cpi = events[0]
    assert cpi.currency == "USD"
    assert cpi.impact == "high"
    assert cpi.name == "CPI m/m"
    assert cpi.forecast == "0.3%"
    ecb = events[1]
    assert ecb.currency == "EUR"
    assert ecb.impact == "medium"
    assert ecb.event_time.date() == base_date.date()
```

- [ ] **Step 3: Implement `src/ig_qt/collector/forex_factory.py`**

```python
"""Forex Factory calendar scraper via Playwright."""
from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime, timezone
from typing import cast

from bs4 import BeautifulSoup, Tag
from dateutil import parser as dtparser
from loguru import logger

from ig_qt.collector.base import NormalizedEvent
from ig_qt.collector.playwright_runner import browser_session

_URL = "https://www.forexfactory.com/calendar"
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(am|pm)$", re.IGNORECASE)
_IMPACT_CLASS = re.compile(r"impact--(high|medium|low|holiday)")


def _impact_from_classes(td: Tag) -> str:
    span = td.find("span", class_=re.compile(r"impact"))
    if not span:
        return "low"
    classes = " ".join(span.get("class", []))
    m = _IMPACT_CLASS.search(classes)
    if not m:
        return "low"
    return m.group(1) if m.group(1) != "holiday" else "low"


def _text(td: Tag | None) -> str:
    return td.get_text(strip=True) if td else ""


def parse_forex_factory_html(html: str, *, fallback_date: datetime) -> list[NormalizedEvent]:
    """Parse Forex Factory calendar HTML into NormalizedEvent list."""
    soup = BeautifulSoup(html, "html.parser")
    events: list[NormalizedEvent] = []
    current_date: date = fallback_date.date()
    for row in soup.select("tr.calendar__row"):
        row_t = cast(Tag, row)
        date_text = _text(row_t.find("td", class_="calendar__date"))
        if date_text:
            try:
                parsed = dtparser.parse(f"{date_text} {fallback_date.year}")
                current_date = parsed.date()
            except (ValueError, TypeError):
                pass
        time_text = _text(row_t.find("td", class_="calendar__time"))
        currency = _text(row_t.find("td", class_="calendar__currency")).upper() or None
        name = _text(row_t.find("td", class_="calendar__event"))
        if not name:
            continue
        impact_td = row_t.find("td", class_="calendar__impact")
        impact = _impact_from_classes(cast(Tag, impact_td)) if impact_td else "low"
        forecast = _text(row_t.find("td", class_="calendar__forecast")) or None
        previous = _text(row_t.find("td", class_="calendar__previous")) or None
        actual = _text(row_t.find("td", class_="calendar__actual")) or None

        if time_text and _TIME_RE.match(time_text):
            try:
                event_dt_naive = dtparser.parse(f"{current_date.isoformat()} {time_text}")
                event_dt = event_dt_naive.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                event_dt = datetime.combine(current_date, datetime.min.time(), tzinfo=timezone.utc)
        else:
            event_dt = datetime.combine(current_date, datetime.min.time(), tzinfo=timezone.utc)

        events.append(
            NormalizedEvent(
                source="forex_factory",
                event_time=event_dt,
                country=None,
                currency=currency,
                name=name,
                impact=impact,
                forecast=forecast,
                previous=previous,
                actual=actual,
            )
        )
    return events


class ForexFactorySource:
    name = "forex_factory"

    def __init__(self, *, timezone_id: str = "Asia/Jakarta") -> None:
        self._timezone_id = timezone_id

    async def fetch_events(self) -> Sequence[NormalizedEvent]:
        try:
            async with browser_session(timezone_id=self._timezone_id) as ctx:
                page = await ctx.new_page()
                await page.goto(_URL, wait_until="networkidle", timeout=45_000)
                await page.wait_for_selector("table.calendar__table", timeout=15_000)
                html = await page.content()
        except Exception as exc:
            logger.warning("forex_factory_fetch_failed error={}", exc)
            return []
        events = parse_forex_factory_html(html, fallback_date=datetime.now(timezone.utc))
        logger.info("forex_factory_fetched count={}", len(events))
        return events
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/collector/test_forex_factory.py -v
uv run mypy --strict src/ig_qt/collector/forex_factory.py
git add src/ig_qt/collector/forex_factory.py tests/collector/fixtures/ff_sample.html tests/collector/test_forex_factory.py
git commit -m "feat(collector): add Forex Factory scraper via Playwright"
```

---

## Task 2.9: Pipeline orchestrator + `collect` CLI

**Files:**
- Create: `src/ig_qt/collector/pipeline.py`
- Modify: `src/ig_qt/__main__.py`
- Create: `tests/collector/test_pipeline.py`

- [ ] **Step 1: Write failing test**

`tests/collector/test_pipeline.py`:

```python
"""Tests for collector pipeline orchestrator."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ig_qt.collector.base import NormalizedEvent, NormalizedNews
from ig_qt.collector.pipeline import CollectorPipeline
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Event, RawNews
from sqlalchemy import select


class _StubNews:
    name = "stub_news"

    async def fetch_news(self) -> Sequence[NormalizedNews]:
        return [
            NormalizedNews(
                source="stub_news",
                external_id="1",
                published_at=datetime(2026, 5, 17, tzinfo=timezone.utc),
                title="Hello World",
                summary=None,
                url="https://x",
                keywords=[],
                raw_payload={},
            ),
        ]


class _FailingNews:
    name = "broken"

    async def fetch_news(self) -> Sequence[NormalizedNews]:
        raise RuntimeError("boom")


class _StubCal:
    name = "stub_cal"

    async def fetch_events(self) -> Sequence[NormalizedEvent]:
        return [
            NormalizedEvent(
                source="stub_cal",
                event_time=datetime(2026, 5, 17, 12, tzinfo=timezone.utc),
                country=None,
                currency="USD",
                name="X",
                impact="high",
                forecast=None,
                previous=None,
                actual=None,
            ),
        ]


@pytest.mark.asyncio
async def test_pipeline_runs_all_sources_isolating_failures(tmp_path: Path) -> None:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    pipe = CollectorPipeline(
        engine=engine,
        news_sources=[_StubNews(), _FailingNews()],
        calendar_sources=[_StubCal()],
    )
    result = await pipe.run_once()
    assert result.news_inserted == 1
    assert result.events_inserted == 1
    assert "broken" in result.failed_sources

    with session_scope(engine) as s:
        assert len(s.execute(select(RawNews)).scalars().all()) == 1
        assert len(s.execute(select(Event)).scalars().all()) == 1
```

- [ ] **Step 2: Implement `src/ig_qt/collector/pipeline.py`**

```python
"""Collector orchestration: run all enabled sources, insert with dedup."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from loguru import logger
from sqlalchemy import Engine

from ig_qt.collector.base import NormalizedEvent, NormalizedNews
from ig_qt.collector.dedup import insert_events_dedup, insert_news_dedup
from ig_qt.db import session_scope


@runtime_checkable
class _NewsSource(Protocol):
    name: str
    async def fetch_news(self) -> Sequence[NormalizedNews]: ...


@runtime_checkable
class _CalSource(Protocol):
    name: str
    async def fetch_events(self) -> Sequence[NormalizedEvent]: ...


@dataclass(frozen=True, slots=True)
class CollectResult:
    news_inserted: int
    events_inserted: int
    failed_sources: list[str] = field(default_factory=list)


class CollectorPipeline:
    def __init__(
        self,
        *,
        engine: Engine,
        news_sources: Sequence[_NewsSource],
        calendar_sources: Sequence[_CalSource],
    ) -> None:
        self._engine = engine
        self._news_sources = list(news_sources)
        self._calendar_sources = list(calendar_sources)

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

        for src in self._calendar_sources:
            try:
                items = await src.fetch_events()
                all_events.extend(items)
            except Exception as exc:
                logger.warning("source_failed name={} error={}", src.name, exc)
                failed.append(src.name)

        with session_scope(self._engine) as s:
            news_n = insert_news_dedup(s, all_news)
            events_n = insert_events_dedup(s, all_events)

        result = CollectResult(
            news_inserted=news_n, events_inserted=events_n, failed_sources=failed
        )
        logger.info(
            "collector_run_done news={} events={} failed={}",
            result.news_inserted,
            result.events_inserted,
            result.failed_sources,
        )
        return result
```

- [ ] **Step 3: Run test (should pass)**

```bash
uv run pytest tests/collector/test_pipeline.py -v
```

- [ ] **Step 4: Build sources from config (factory function)**

Append to `src/ig_qt/collector/pipeline.py`:

```python
def build_pipeline_from_config(engine: Engine, cfg) -> CollectorPipeline:  # type: ignore[no-untyped-def]
    """Build pipeline using AppConfig.collector flags."""
    from ig_qt.collector.forex_factory import ForexFactorySource
    from ig_qt.collector.gnews import GNewsSource
    from ig_qt.collector.news_api import NewsAPISource

    news_sources: list[_NewsSource] = []
    if cfg.collector.news_api_enabled and cfg.collector.news_api_key:
        news_sources.append(
            NewsAPISource(api_key=cfg.collector.news_api_key.get_secret_value())
        )
    if cfg.collector.gnews_enabled and cfg.collector.gnews_key:
        news_sources.append(
            GNewsSource(api_key=cfg.collector.gnews_key.get_secret_value())
        )

    cal_sources: list[_CalSource] = []
    if cfg.collector.forex_factory_enabled:
        cal_sources.append(ForexFactorySource(timezone_id=cfg.schedule.timezone))

    return CollectorPipeline(
        engine=engine, news_sources=news_sources, calendar_sources=cal_sources
    )
```

- [ ] **Step 5: Wire `collect --once` into `__main__.py`**

Replace `src/ig_qt/__main__.py`:

```python
"""Entry point: `python -m ig_qt`."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from ig_qt.app import run_check, run_collect_once


def main() -> int:
    parser = argparse.ArgumentParser(prog="ig_qt")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("check", help="Validate env + DB and exit")
    collect = sub.add_parser("collect", help="Run collector once")
    collect.add_argument("--once", action="store_true", default=True)
    parser.add_argument("--check", action="store_true", help="Alias for `check` subcommand")
    args = parser.parse_args()

    if args.check or args.cmd == "check":
        return run_check(config_path=args.config)
    if args.cmd == "collect":
        return asyncio.run(run_collect_once(config_path=args.config))
    print("ig_qt: scheduler entry point not implemented yet (M5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Add `run_collect_once` to `src/ig_qt/app.py`**

Append:

```python
async def run_collect_once(*, config_path: Path) -> int:
    """One-shot collector run for manual invocation / testing."""
    from ig_qt.collector.pipeline import build_pipeline_from_config

    cfg = load_config(config_path)
    log_dir = cfg.paths.data_dir / "logs"
    configure_logging(log_dir=log_dir, level="INFO", json_logs=True)
    db_path = cfg.paths.data_dir / "ig_qt.db"
    engine = build_engine(db_path)
    init_schema(engine)
    pipeline = build_pipeline_from_config(engine, cfg)
    result = await pipeline.run_once()
    logger.info(
        "collect_done news={} events={} failed={}",
        result.news_inserted,
        result.events_inserted,
        result.failed_sources,
    )
    return 0 if not result.failed_sources else 1
```

- [ ] **Step 7: Run full suite**

```bash
uv run pytest -v
uv run mypy --strict src/
uv run ruff check src/ tests/
```

Expected: ALL PASS / clean.

- [ ] **Step 8: Commit**

```bash
git add src/ig_qt/collector/pipeline.py src/ig_qt/app.py src/ig_qt/__main__.py tests/collector/test_pipeline.py
git commit -m "feat(collector): orchestrate sources via pipeline + add collect CLI"
```

---

## M2 Acceptance Criteria

- [ ] All Task 2.x tests green: `uv run pytest tests/collector -v`
- [ ] `uv run mypy --strict src/ig_qt/collector/` clean
- [ ] `uv run python -m ig_qt collect` (with valid `.env`) successfully fetches and inserts; check counts via `sqlite3 data/ig_qt.db "select count(*) from raw_news; select count(*) from events;"`
- [ ] Per-source failure isolated: kill NewsAPI key → other sources still run; `failed_sources` includes `newsapi`
- [ ] Dedup verified: run `collect` twice → second run inserts 0 (dedup_key collisions)
- [ ] Each task committed individually

## M2 Self-Review Notes

- **Forex Factory parser is fragile by design.** Selectors come from current FF DOM. If FF redesigns, fixture-based test will catch (red CI), then update parser. Production runs that get 0 events should trigger Telegram alert — wired in M5.
- **yfinance is sync.** `asyncio.to_thread` keeps event loop unblocked. Don't await inside the thread.
- **News dedup happens cross-source.** If NewsAPI and GNews both report same headline, second insert skipped. That's intentional — analyst sees one row.
- **Calendar fixture HTML is minimal.** Real FF page has thousands of rows + nested tables. Production `wait_for_selector` waits for `table.calendar__table`, which guarantees at least the table is rendered before parse.
- **Pipeline does not retry sources.** Per-source adapter handles retries via tenacity. If adapter raises, pipeline records failure and moves on.
