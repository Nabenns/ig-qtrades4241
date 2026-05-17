# M4 Composer — Implementation Plan

> **Parent:** [`../2026-05-17-ig-forex-automation.md`](../2026-05-17-ig-forex-automation.md)
> **Prereq:** M1 + M2 + M3 complete.

**Goal:** Convert `post_drafts` into ready-to-publish `posts` rows with finalized captions and rendered visual assets on disk. Three visual rendering paths (chart via mplfinance, headline/event/recap cards via HTML+Playwright). Hard image format compliance (1080×1080 feed, 1080×1920 story, sRGB JPEG ≤8MB). End state: `python -m ig_qt compose --once` processes all `pending` drafts and produces `posts.status='ready'` with PNG/JPG files under `data/posts/<post_id>/`.

**Files created in M4:**
- `src/ig_qt/composer/__init__.py`, `runner.py`, `caption.py`
- `src/ig_qt/composer/chart_renderer.py`, `html_renderer.py`, `pillow_fallback.py`, `postprocess.py`
- `src/ig_qt/composer/stories.py` (event reminder + market recap helpers)
- `templates/base.css`, `templates/headline_card.html`, `templates/event_card.html`, `templates/market_recap.html`
- `assets/logo.png` (placeholder)
- `tests/composer/test_*.py`
- Modify: `pyproject.toml` (add deps), `src/ig_qt/app.py`, `src/ig_qt/__main__.py`

**New dependencies:** `mplfinance>=0.12.10`, `pandas>=2.2`, `pillow>=10.4`, `jinja2>=3.1`.

---

## Task 4.1: Brand assets + dependencies + scaffolding

**Files:**
- Modify: `pyproject.toml`
- Create: `assets/logo.png` (placeholder 256×256 PNG)
- Create: `templates/base.css`
- Create: `src/ig_qt/composer/__init__.py`

**Depends on:** OD-3 (brand assets ready). If user has logo + brand colors, replace placeholder. Otherwise plan defaults work.

- [ ] **Step 1: Add deps to `pyproject.toml`**

Append to `[project] dependencies`:

```toml
    "mplfinance>=0.12.10",
    "pandas>=2.2",
    "pillow>=10.4",
    "jinja2>=3.1",
```

- [ ] **Step 2: Sync**

```bash
uv sync
```

- [ ] **Step 3: Create placeholder logo**

```bash
uv run python -c "from PIL import Image, ImageDraw, ImageFont; img = Image.new('RGBA', (256, 256), (10, 132, 255, 255)); d = ImageDraw.Draw(img); d.ellipse((40, 40, 216, 216), fill=(255, 255, 255, 255)); d.text((90, 100), 'IGQ', fill=(10, 132, 255, 255)); img.save('assets/logo.png')"
```

Replace later with real logo. Path is configurable via `config.yaml` `brand.logo_path`.

- [ ] **Step 4: Create `templates/base.css`**

```css
:root {
  --bg: #0b1220;
  --surface: #0f172a;
  --primary: #0a84ff;
  --accent: #ffb020;
  --text: #f8fafc;
  --muted: #94a3b8;
  --positive: #26a69a;
  --negative: #ef5350;
  --high: #ef4444;
  --medium: #f59e0b;
  --low: #6b7280;
  --font-display: "Inter", "Helvetica Neue", Arial, sans-serif;
  --font-mono: "JetBrains Mono", "IBM Plex Mono", monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font-display);
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
  width: 1080px;
  height: 1080px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 64px;
  position: relative;
}

body.story {
  height: 1920px;
  padding: 96px 64px;
}

.brand-strip {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 12px;
  background: linear-gradient(90deg, var(--primary), var(--accent));
}

.handle {
  position: absolute;
  bottom: 32px;
  right: 64px;
  font-size: 22px;
  color: var(--muted);
  letter-spacing: 0.05em;
}

.label-pill {
  display: inline-block;
  padding: 8px 18px;
  border-radius: 999px;
  background: rgba(10, 132, 255, 0.18);
  color: var(--primary);
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.headline {
  font-size: 86px;
  font-weight: 700;
  line-height: 1.05;
  letter-spacing: -0.02em;
  margin-top: 32px;
}

.subhead {
  font-size: 36px;
  color: var(--muted);
  line-height: 1.3;
  margin-top: 24px;
}

.summary {
  font-size: 28px;
  color: var(--text);
  line-height: 1.5;
  margin-top: auto;
  max-height: 360px;
  overflow: hidden;
}

.event-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  margin-top: 48px;
}

.event-card {
  background: var(--surface);
  border-radius: 24px;
  padding: 32px;
  border-left: 8px solid var(--medium);
}
.event-card.high { border-left-color: var(--high); }
.event-card.low  { border-left-color: var(--low); }

.event-time { font-size: 24px; color: var(--muted); }
.event-name { font-size: 36px; font-weight: 600; margin-top: 8px; }
.event-meta { font-size: 22px; color: var(--muted); margin-top: 16px; }

.recap-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-top: 48px;
}

.recap-card {
  background: var(--surface);
  border-radius: 20px;
  padding: 28px;
}
.recap-symbol { font-size: 32px; font-weight: 700; }
.recap-change { font-size: 56px; font-weight: 700; margin-top: 8px; font-family: var(--font-mono); }
.recap-change.up { color: var(--positive); }
.recap-change.down { color: var(--negative); }
.recap-close { font-size: 20px; color: var(--muted); margin-top: 8px; font-family: var(--font-mono); }

.logo-corner {
  position: absolute;
  bottom: 32px;
  left: 64px;
  width: 88px;
  height: 88px;
}
```

- [ ] **Step 5: Create `src/ig_qt/composer/__init__.py`**

```python
"""Caption finalization and visual rendering."""
from __future__ import annotations
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock assets/logo.png templates/base.css src/ig_qt/composer/__init__.py
git commit -m "chore(composer): add deps, brand stylesheet, and placeholder logo"
```

---

## Task 4.2: Caption finalizer

**Files:**
- Create: `src/ig_qt/composer/caption.py`
- Create: `tests/composer/__init__.py`
- Create: `tests/composer/test_caption.py`

- [ ] **Step 1: Write failing test**

`tests/composer/test_caption.py`:

```python
"""Tests for caption finalizer."""
from __future__ import annotations

import pytest

from ig_qt.composer.caption import (
    DISCLAIMER,
    finalize_caption,
    pick_opener,
    substitute_placeholders,
)


def test_pick_opener_returns_one_of_pool() -> None:
    op = pick_opener(seed=1)
    assert isinstance(op, str)
    assert len(op) > 0


def test_pick_opener_seed_deterministic() -> None:
    assert pick_opener(seed=42) == pick_opener(seed=42)


def test_substitute_placeholders_replaces_known_keys() -> None:
    text = "EUR/USD close: {eurusd_close}, USD/JPY: {usdjpy_close}"
    result = substitute_placeholders(
        text, prices={"EUR/USD": 1.0865, "USD/JPY": 158.42}
    )
    assert "1.0865" in result
    assert "158.42" in result


def test_substitute_placeholders_strips_unresolved() -> None:
    text = "Today {unknown_key} matters"
    result = substitute_placeholders(text, prices={})
    # Unresolved placeholders are removed (not left as garbage)
    assert "{unknown_key}" not in result


def test_finalize_caption_appends_disclaimer_when_required() -> None:
    out = finalize_caption(
        opener="Update pasar:",
        body="Fed hawkish, USD strong.",
        hashtags=["#forex", "#fed", "#trading"],
        cta="🔔 Follow @x",
        disclaimer_required=True,
        prices={},
    )
    assert DISCLAIMER in out
    assert "Update pasar:" in out
    assert "#forex" in out
    assert "Follow @x" in out


def test_finalize_caption_no_disclaimer_when_not_required() -> None:
    out = finalize_caption(
        opener="Hi", body="x", hashtags=[], cta="", disclaimer_required=False, prices={}
    )
    assert DISCLAIMER not in out


def test_finalize_caption_truncates_to_ig_limit() -> None:
    body = "x" * 2300
    out = finalize_caption(
        opener="A", body=body, hashtags=["#a"], cta="", disclaimer_required=False, prices={}
    )
    assert len(out) <= 2200
```

- [ ] **Step 2: Implement `src/ig_qt/composer/caption.py`**

```python
"""Caption finalization: opener variation, placeholder substitution, disclaimer, hashtags, CTA."""
from __future__ import annotations

import random
import re
from collections.abc import Mapping, Sequence

DISCLAIMER = (
    "_*Bukan rekomendasi trading. Lakukan riset sendiri & kelola risiko.*_"
)

_OPENERS: tuple[str, ...] = (
    "Update pasar hari ini:",
    "Yang lagi happening di pasar:",
    "Highlight macro hari ini:",
    "Forex watch:",
    "Market context yang lagi panas:",
    "Recap pasar:",
    "Yang perlu kamu tahu hari ini:",
    "Sorotan trading hari ini:",
    "Macro check:",
    "Hot takes pasar:",
    "Forex briefing:",
    "Konteks pasar terkini:",
    "Update penting buat trader:",
    "Pasar lagi gerak gini:",
    "Fokus market hari ini:",
    "Risk-on atau risk-off?",
    "Daily forex digest:",
    "Pasar bicara apa hari ini?",
    "Setup pasar yang menarik:",
    "Briefing harian forex:",
)

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_]+)\}")

# Map placeholder key → symbol lookup
_PLACEHOLDER_TO_SYMBOL: Mapping[str, str] = {
    "eurusd_close": "EUR/USD",
    "gbpusd_close": "GBP/USD",
    "usdjpy_close": "USD/JPY",
    "xauusd_close": "XAU/USD",
    "dxy_close": "DXY",
    "btcusd_close": "BTC/USD",
}


def pick_opener(*, seed: int | None = None) -> str:
    rng = random.Random(seed) if seed is not None else random
    return rng.choice(_OPENERS)


def substitute_placeholders(text: str, *, prices: Mapping[str, float]) -> str:
    """Replace `{eurusd_close}` style tokens with formatted prices. Strip unresolved."""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).lower()
        symbol = _PLACEHOLDER_TO_SYMBOL.get(key)
        if symbol is None or symbol not in prices:
            return ""
        val = prices[symbol]
        return f"{val:.4f}" if val < 100 else f"{val:.2f}"

    result = _PLACEHOLDER_RE.sub(replace, text)
    # Collapse double spaces left by removed placeholders.
    return re.sub(r"\s{2,}", " ", result).strip()


def finalize_caption(
    *,
    opener: str,
    body: str,
    hashtags: Sequence[str],
    cta: str,
    disclaimer_required: bool,
    prices: Mapping[str, float],
    max_chars: int = 2200,
) -> str:
    """Assemble final caption respecting IG 2200-char limit."""
    body_filled = substitute_placeholders(body, prices=prices)
    parts: list[str] = [opener, "", body_filled]
    if disclaimer_required:
        parts.extend(["", DISCLAIMER])
    if cta:
        parts.extend(["", cta])
    if hashtags:
        # Cap at 15 hashtags
        tag_block = " ".join(hashtags[:15])
        parts.extend(["", tag_block])
    full = "\n".join(parts).strip()
    if len(full) > max_chars:
        # Trim body so total fits
        overflow = len(full) - max_chars
        new_body = body_filled[: max(0, len(body_filled) - overflow - 4)] + "..."
        parts = [opener, "", new_body]
        if disclaimer_required:
            parts.extend(["", DISCLAIMER])
        if cta:
            parts.extend(["", cta])
        if hashtags:
            parts.extend(["", " ".join(hashtags[:15])])
        full = "\n".join(parts).strip()
    return full[:max_chars]
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/composer/test_caption.py -v
uv run mypy --strict src/ig_qt/composer/caption.py
git add src/ig_qt/composer/caption.py tests/composer/__init__.py tests/composer/test_caption.py
git commit -m "feat(composer): add caption finalizer with opener pool and placeholders"
```

---

## Task 4.3: Image post-processing (resize, watermark, sRGB JPEG)

**Files:**
- Create: `src/ig_qt/composer/postprocess.py`
- Create: `tests/composer/test_postprocess.py`

- [ ] **Step 1: Write failing test**

`tests/composer/test_postprocess.py`:

```python
"""Tests for image post-processing."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from ig_qt.composer.postprocess import (
    finalize_feed_image,
    finalize_story_image,
)


def _make_test_image(path: Path, size: tuple[int, int]) -> None:
    img = Image.new("RGB", size, (15, 23, 42))
    img.save(path, "PNG")


def test_finalize_feed_resizes_to_1080x1080(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    _make_test_image(src, (2000, 2000))
    logo = tmp_path / "logo.png"
    _make_test_image(logo, (256, 256))
    dst = tmp_path / "out.jpg"
    out = finalize_feed_image(src=src, dst=dst, logo_path=logo, handle="@x")
    img = Image.open(out)
    assert img.size == (1080, 1080)
    assert img.mode == "RGB"
    assert dst.stat().st_size < 8 * 1024 * 1024


def test_finalize_story_resizes_to_1080x1920(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    _make_test_image(src, (1200, 2000))
    logo = tmp_path / "logo.png"
    _make_test_image(logo, (256, 256))
    dst = tmp_path / "out.jpg"
    out = finalize_story_image(src=src, dst=dst, logo_path=logo, handle="@x")
    img = Image.open(out)
    assert img.size == (1080, 1920)


def test_recompresses_when_oversize(tmp_path: Path) -> None:
    # Generate intentionally large source by using high resolution noise
    import numpy as np

    arr = (np.random.rand(2200, 2200, 3) * 255).astype("uint8")
    src = tmp_path / "src.png"
    Image.fromarray(arr).save(src, "PNG")
    logo = tmp_path / "logo.png"
    Image.new("RGB", (256, 256), (255, 0, 0)).save(logo, "PNG")
    dst = tmp_path / "out.jpg"
    finalize_feed_image(src=src, dst=dst, logo_path=logo, handle="@x")
    assert dst.stat().st_size < 8 * 1024 * 1024
```

- [ ] **Step 2: Implement `src/ig_qt/composer/postprocess.py`**

```python
"""Final image post-processing: resize, watermark, sRGB JPEG with size cap."""
from __future__ import annotations

from pathlib import Path

from loguru import logger
from PIL import Image, ImageDraw, ImageFont

_MAX_BYTES = 8 * 1024 * 1024


def _open_rgb(src: Path) -> Image.Image:
    img = Image.open(src)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _resize_cover(img: Image.Image, target: tuple[int, int]) -> Image.Image:
    """Resize covering target box (no letterboxing, may crop)."""
    tw, th = target
    sw, sh = img.size
    scale = max(tw / sw, th / sh)
    new_w, new_h = int(sw * scale), int(sh * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _paste_logo(canvas: Image.Image, logo_path: Path, *, handle: str) -> Image.Image:
    if not logo_path.exists():
        logger.warning("postprocess_logo_missing path={}", logo_path)
        return canvas
    logo = Image.open(logo_path).convert("RGBA")
    logo_size = 96
    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
    x = canvas.width - logo_size - 56
    y = canvas.height - logo_size - 56
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.paste(logo, (x, y), logo)
    draw = ImageDraw.Draw(canvas_rgba)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    draw.text((56, canvas.height - 56), handle, fill=(255, 255, 255, 230), font=font)
    return canvas_rgba.convert("RGB")


def _save_jpeg_capped(img: Image.Image, dst: Path) -> None:
    """Save JPEG, re-compress with lower quality if file > 8MB."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    quality = 92
    while quality >= 60:
        img.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
        if dst.stat().st_size <= _MAX_BYTES:
            logger.debug("postprocess_saved quality={} bytes={}", quality, dst.stat().st_size)
            return
        logger.warning("postprocess_oversize quality={} bytes={}", quality, dst.stat().st_size)
        quality -= 10
    logger.error("postprocess_could_not_compress path={}", dst)


def finalize_feed_image(
    *, src: Path, dst: Path, logo_path: Path, handle: str
) -> Path:
    img = _open_rgb(src)
    img = _resize_cover(img, (1080, 1080))
    img = _paste_logo(img, logo_path, handle=handle)
    _save_jpeg_capped(img, dst)
    return dst


def finalize_story_image(
    *, src: Path, dst: Path, logo_path: Path, handle: str
) -> Path:
    img = _open_rgb(src)
    img = _resize_cover(img, (1080, 1920))
    img = _paste_logo(img, logo_path, handle=handle)
    _save_jpeg_capped(img, dst)
    return dst
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/composer/test_postprocess.py -v
uv run mypy --strict src/ig_qt/composer/postprocess.py
git add src/ig_qt/composer/postprocess.py tests/composer/test_postprocess.py
git commit -m "feat(composer): add image post-processing with size cap"
```

---

## Task 4.4: HTML+Playwright renderer (cards)

**Files:**
- Create: `templates/headline_card.html`
- Create: `templates/event_card.html`
- Create: `templates/market_recap.html`
- Create: `src/ig_qt/composer/html_renderer.py`
- Create: `tests/composer/test_html_renderer.py`

- [ ] **Step 1: Create `templates/headline_card.html`**

```html
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>{{ base_css }}</style>
</head>
<body class="{{ orientation }}">
<div class="brand-strip"></div>
<span class="label-pill">{{ label | default("Forex News") }}</span>
<h1 class="headline">{{ headline }}</h1>
{% if subheadline %}<p class="subhead">{{ subheadline }}</p>{% endif %}
<p class="summary">{{ summary }}</p>
<div class="handle">{{ handle }}</div>
</body>
</html>
```

- [ ] **Step 2: Create `templates/event_card.html`**

```html
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>{{ base_css }}</style>
</head>
<body class="{{ orientation }}">
<div class="brand-strip"></div>
<span class="label-pill">Event Hari Ini</span>
<h1 class="headline">{{ headline }}</h1>
{% if subheadline %}<p class="subhead">{{ subheadline }}</p>{% endif %}
<div class="event-grid">
{% for ev in events %}
  <div class="event-card {{ ev.impact }}">
    <div class="event-time">{{ ev.time }} WIB · {{ ev.currency }}</div>
    <div class="event-name">{{ ev.name }}</div>
    <div class="event-meta">
      forecast {{ ev.forecast or "—" }} · prev {{ ev.previous or "—" }}
    </div>
  </div>
{% endfor %}
</div>
<div class="handle">{{ handle }}</div>
</body>
</html>
```

- [ ] **Step 3: Create `templates/market_recap.html`**

```html
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<style>{{ base_css }}</style>
</head>
<body class="{{ orientation }}">
<div class="brand-strip"></div>
<span class="label-pill">Market Recap</span>
<h1 class="headline">{{ headline }}</h1>
{% if subheadline %}<p class="subhead">{{ subheadline }}</p>{% endif %}
<div class="recap-grid">
{% for r in recaps %}
  <div class="recap-card">
    <div class="recap-symbol">{{ r.symbol }}</div>
    <div class="recap-change {{ 'up' if r.change_pct >= 0 else 'down' }}">
      {{ "%+.2f"|format(r.change_pct) }}%
    </div>
    <div class="recap-close">{{ r.close }}</div>
  </div>
{% endfor %}
</div>
<div class="handle">{{ handle }}</div>
</body>
</html>
```

- [ ] **Step 4: Write failing test**

`tests/composer/test_html_renderer.py`:

```python
"""Tests for HTML renderer."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from ig_qt.composer.html_renderer import render_card


@pytest.mark.asyncio
async def test_render_headline_card_produces_png(tmp_path: Path) -> None:
    out = tmp_path / "headline.png"
    await render_card(
        template="headline_card.html",
        context={
            "headline": "Fed Holds Rates Hawkish",
            "subheadline": "USD set to strengthen short-term",
            "summary": "FOMC keeps rates at 5.25-5.50%, signals one more hike possible.",
            "label": "Macro Watch",
            "handle": "@x",
            "orientation": "feed",
        },
        out_path=out,
        viewport=(1080, 1080),
    )
    assert out.exists()
    img = Image.open(out)
    assert img.size == (1080, 1080)


@pytest.mark.asyncio
async def test_render_event_card_with_two_events(tmp_path: Path) -> None:
    out = tmp_path / "event.png"
    await render_card(
        template="event_card.html",
        context={
            "headline": "Event Hari Ini",
            "subheadline": "2 high-impact events",
            "events": [
                {"time": "12:30", "currency": "USD", "name": "CPI m/m", "impact": "high",
                 "forecast": "0.3%", "previous": "0.4%"},
                {"time": "20:00", "currency": "EUR", "name": "ECB Rate", "impact": "high",
                 "forecast": "4.50%", "previous": "4.50%"},
            ],
            "handle": "@x",
            "orientation": "story",
        },
        out_path=out,
        viewport=(1080, 1920),
    )
    img = Image.open(out)
    assert img.size == (1080, 1920)
```

- [ ] **Step 5: Implement `src/ig_qt/composer/html_renderer.py`**

```python
"""Render HTML templates to PNG via Playwright."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape
from loguru import logger

from ig_qt.collector.playwright_runner import browser_session

_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
_BASE_CSS_PATH = _TEMPLATES_DIR / "base.css"


def _build_env() -> Environment:
    return Environment(
        loader=ChoiceLoader([FileSystemLoader(str(_TEMPLATES_DIR))]),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


async def render_card(
    *,
    template: str,
    context: dict[str, Any],
    out_path: Path,
    viewport: tuple[int, int],
) -> Path:
    """Render Jinja template, screenshot via headless Chromium, save PNG."""
    env = _build_env()
    base_css = _BASE_CSS_PATH.read_text(encoding="utf-8")
    ctx = {**context, "base_css": base_css}
    html = env.get_template(template).render(**ctx)

    async with browser_session() as browser_ctx:
        page = await browser_ctx.new_page()
        await page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
        await page.set_content(html, wait_until="networkidle", timeout=15_000)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(out_path), full_page=False, type="png")
    logger.info("html_render_done template={} out={}", template, out_path)
    return out_path
```

- [ ] **Step 6: Run + commit**

```bash
uv run pytest tests/composer/test_html_renderer.py -v
uv run mypy --strict src/ig_qt/composer/html_renderer.py
git add templates/ src/ig_qt/composer/html_renderer.py tests/composer/test_html_renderer.py
git commit -m "feat(composer): add HTML+Playwright card renderer"
```

---

## Task 4.5: mplfinance chart renderer

**Files:**
- Create: `src/ig_qt/composer/chart_renderer.py`
- Create: `tests/composer/test_chart_renderer.py`

- [ ] **Step 1: Write failing test**

`tests/composer/test_chart_renderer.py`:

```python
"""Tests for chart renderer."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from ig_qt.composer.chart_renderer import render_chart_png


def _ohlc_fixture(n: int = 100) -> list[dict[str, float | str]]:
    import math

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
    assert img.size[0] >= 1000  # mplfinance may pad slightly


def test_render_chart_raises_when_too_few_candles(tmp_path: Path) -> None:
    out = tmp_path / "chart.png"
    import pytest

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
```

- [ ] **Step 2: Implement `src/ig_qt/composer/chart_renderer.py`**

```python
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
        tight_layout=True,
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
        0.99, 1.02, headline, transform=main_ax.transAxes, color="#94a3b8",
        ha="right", va="bottom", fontsize=18,
    )
    for ann in annotations[:4]:
        # annotation format like "1.0870 resistance" or "Fed event"
        first_token = ann.split()[0]
        try:
            level = float(first_token)
            main_ax.axhline(level, color="#ffb020", linewidth=1.2, alpha=0.7, linestyle="--")
            main_ax.text(
                df.index[-1], level, f"  {ann}",
                color="#ffb020", fontsize=14, va="center",
            )
        except ValueError:
            continue

    fig.savefig(
        out_path,
        dpi=100,
        bbox_inches="tight",
        facecolor="#0b1220",
        format="png",
    )
    logger.info("chart_render_done symbol={} out={}", symbol, out_path)
    return out_path
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/composer/test_chart_renderer.py -v
uv run mypy --strict src/ig_qt/composer/chart_renderer.py
git add src/ig_qt/composer/chart_renderer.py tests/composer/test_chart_renderer.py
git commit -m "feat(composer): add mplfinance chart renderer"
```

---

## Task 4.6: Pillow fallback renderer

**Files:**
- Create: `src/ig_qt/composer/pillow_fallback.py`
- Create: `tests/composer/test_pillow_fallback.py`

- [ ] **Step 1: Write failing test**

`tests/composer/test_pillow_fallback.py`:

```python
"""Tests for Pillow fallback renderer (used when Playwright + mplfinance fail)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from ig_qt.composer.pillow_fallback import render_text_card


def test_render_text_card_produces_image(tmp_path: Path) -> None:
    out = tmp_path / "fallback.png"
    render_text_card(
        headline="Fed Hawkish",
        body="USD strengthens after FOMC minutes",
        out_path=out,
        size=(1080, 1080),
    )
    assert out.exists()
    img = Image.open(out)
    assert img.size == (1080, 1080)
```

- [ ] **Step 2: Implement `src/ig_qt/composer/pillow_fallback.py`**

```python
"""Last-resort renderer using only Pillow (no Playwright/mplfinance)."""
from __future__ import annotations

import textwrap
from pathlib import Path

from loguru import logger
from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_text_card(
    *,
    headline: str,
    body: str,
    out_path: Path,
    size: tuple[int, int],
) -> Path:
    img = Image.new("RGB", size, (11, 18, 32))
    draw = ImageDraw.Draw(img)
    # Top accent strip
    draw.rectangle([(0, 0), (size[0], 12)], fill=(10, 132, 255))

    headline_font = _load_font(72)
    body_font = _load_font(32)

    margin = 80
    y = margin + 40
    headline_lines = textwrap.wrap(headline, width=24)
    for line in headline_lines:
        draw.text((margin, y), line, fill=(248, 250, 252), font=headline_font)
        y += 90
    y += 40
    body_lines = textwrap.wrap(body, width=42)
    for line in body_lines[:8]:
        draw.text((margin, y), line, fill=(148, 163, 184), font=body_font)
        y += 50

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    logger.warning("pillow_fallback_render path={}", out_path)
    return out_path
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/composer/test_pillow_fallback.py -v
uv run mypy --strict src/ig_qt/composer/pillow_fallback.py
git add src/ig_qt/composer/pillow_fallback.py tests/composer/test_pillow_fallback.py
git commit -m "feat(composer): add Pillow fallback renderer"
```

---

## Task 4.7: Story builders (event reminder + market recap)

**Files:**
- Create: `src/ig_qt/composer/stories.py`
- Create: `tests/composer/test_stories.py`

- [ ] **Step 1: Write failing test**

`tests/composer/test_stories.py`:

```python
"""Tests for story builders."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ig_qt.composer.stories import build_event_reminder_context, build_market_recap_context


def test_build_event_reminder_filters_high_medium_only() -> None:
    today = datetime(2026, 5, 17, tzinfo=timezone.utc)
    events: list[Any] = [
        type("E", (), {
            "event_time": today + timedelta(hours=2), "currency": "USD",
            "name": "CPI", "impact": "high", "forecast": "0.3%", "previous": "0.4%",
        }),
        type("E", (), {
            "event_time": today + timedelta(hours=4), "currency": "EUR",
            "name": "Speech", "impact": "low", "forecast": None, "previous": None,
        }),
    ]
    ctx = build_event_reminder_context(events=events, now=today)
    assert len(ctx["events"]) == 1
    assert ctx["events"][0]["currency"] == "USD"


def test_build_market_recap_calculates_change() -> None:
    prices = {
        "EUR/USD": [
            {"t": "2026-05-16T00:00:00+00:00", "open": 1.0800, "high": 1.0810, "low": 1.0790, "close": 1.0850},
            {"t": "2026-05-17T00:00:00+00:00", "open": 1.0850, "high": 1.0880, "low": 1.0840, "close": 1.0875},
        ],
    }
    ctx = build_market_recap_context(latest_prices=prices, symbols=["EUR/USD"])
    assert len(ctx["recaps"]) == 1
    assert ctx["recaps"][0]["symbol"] == "EUR/USD"
    assert ctx["recaps"][0]["change_pct"] > 0
```

- [ ] **Step 2: Implement `src/ig_qt/composer/stories.py`**

```python
"""Story content builders: event reminder + market recap. Caption + visual context only."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


class _EventLike(Protocol):
    event_time: datetime
    currency: str | None
    name: str
    impact: str
    forecast: str | None
    previous: str | None


def build_event_reminder_context(
    *,
    events: Sequence[_EventLike],
    now: datetime,
    window_hours: int = 12,
) -> dict[str, Any]:
    end = now + timedelta(hours=window_hours)
    filtered = [
        e
        for e in events
        if e.impact in ("high", "medium") and now <= e.event_time <= end
    ]
    items: list[dict[str, Any]] = []
    for e in filtered[:4]:
        local = e.event_time.astimezone(timezone(timedelta(hours=7)))  # WIB
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
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/composer/test_stories.py -v
uv run mypy --strict src/ig_qt/composer/stories.py
git add src/ig_qt/composer/stories.py tests/composer/test_stories.py
git commit -m "feat(composer): add story context builders for events and recap"
```

---

## Task 4.8: Composer runner (process drafts → posts)

**Files:**
- Create: `src/ig_qt/composer/runner.py`
- Modify: `src/ig_qt/app.py`, `src/ig_qt/__main__.py`
- Create: `tests/composer/test_runner.py`

- [ ] **Step 1: Write failing test**

`tests/composer/test_runner.py`:

```python
"""Tests for composer runner."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from ig_qt.composer.runner import ComposerRunner
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import Post, PostDraft, PriceCache


@pytest.fixture
def seeded(tmp_path: Path) -> Any:
    engine = build_engine(tmp_path / "x.db")
    init_schema(engine)
    with session_scope(engine) as s:
        s.add(
            PostDraft(
                post_type="feed",
                source_news_ids=[],
                topic_tag="fed_hawkish",
                angle="Fed hawkish",
                key_points=["a", "b"],
                caption_draft="Fed hawkish, USD/JPY watch level {usdjpy_close}",
                visual_spec={"type": "headline", "headline": "Fed Hawkish"},
                disclaimer_required=True,
                confidence=0.85,
                llm_provider="mock",
                llm_model="m",
                prompt_version="v1",
                status="pending",
            )
        )
        s.add(
            PriceCache(
                symbol="USD/JPY",
                timeframe="1d",
                fetched_at=datetime.now(timezone.utc),
                ohlc_json=[{"t": "2026-05-17", "open": 158, "high": 159, "low": 157, "close": 158.42}],
            )
        )
    return engine, tmp_path


@pytest.mark.asyncio
async def test_runner_promotes_draft_to_post(seeded: Any) -> None:
    engine, tmp_path = seeded
    runner = ComposerRunner(
        engine=engine,
        data_dir=tmp_path,
        logo_path=tmp_path / "logo.png",
        handle="@x",
        scheduled_for_factory=lambda d: datetime.now(timezone.utc) + timedelta(hours=1),
    )
    # Pre-create logo so postprocess doesn't warn
    from PIL import Image
    Image.new("RGB", (256, 256), (10, 132, 255)).save(tmp_path / "logo.png")

    summary = await runner.run_once()
    assert summary.processed == 1
    assert summary.failed == 0

    with session_scope(engine) as s:
        posts = s.query(Post).all()
        assert len(posts) == 1
        post = posts[0]
        assert post.status == "ready"
        assert "158.42" in post.caption_final  # placeholder substituted
        assert Path(post.asset_path).exists()
        # Draft marked consumed
        drafts = s.query(PostDraft).all()
        assert drafts[0].status == "consumed"
```

- [ ] **Step 2: Implement `src/ig_qt/composer/runner.py`**

```python
"""Compose pending drafts into ready-to-publish posts."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import Engine, select

from ig_qt.analyst.schemas import VisualSpec
from ig_qt.composer.caption import finalize_caption, pick_opener
from ig_qt.composer.chart_renderer import render_chart_png
from ig_qt.composer.html_renderer import render_card
from ig_qt.composer.pillow_fallback import render_text_card
from ig_qt.composer.postprocess import finalize_feed_image, finalize_story_image
from ig_qt.db import session_scope
from ig_qt.models import Post, PostDraft, PriceCache

_DEFAULT_HASHTAGS: tuple[str, ...] = (
    "#forex", "#trading", "#marketupdate", "#usd", "#fed",
    "#economy", "#macroeconomics", "#financialnews", "#globalmarkets",
    "#dollar", "#euro", "#yen", "#tradinglife", "#chartanalysis",
)
_DEFAULT_CTA = "💬 Komentar pendapatmu di bawah"


@dataclass(frozen=True, slots=True)
class ComposeSummary:
    processed: int
    failed: int


class ComposerRunner:
    def __init__(
        self,
        *,
        engine: Engine,
        data_dir: Path,
        logo_path: Path,
        handle: str,
        scheduled_for_factory: Callable[[PostDraft], datetime],
        hashtags: tuple[str, ...] = _DEFAULT_HASHTAGS,
        cta: str = _DEFAULT_CTA,
    ) -> None:
        self._engine = engine
        self._data_dir = data_dir
        self._logo_path = logo_path
        self._handle = handle
        self._sched = scheduled_for_factory
        self._hashtags = hashtags
        self._cta = cta

    def _latest_prices(self, session: Any) -> dict[str, list[dict[str, Any]]]:
        rows = list(session.execute(select(PriceCache)).scalars())
        latest: dict[str, PriceCache] = {}
        for r in rows:
            cur = latest.get(r.symbol)
            if cur is None or r.fetched_at > cur.fetched_at:
                latest[r.symbol] = r
        return {sym: r.ohlc_json for sym, r in latest.items()}

    def _last_close_map(
        self, prices: dict[str, list[dict[str, Any]]]
    ) -> dict[str, float]:
        out: dict[str, float] = {}
        for sym, ohlc in prices.items():
            if ohlc:
                out[sym] = float(ohlc[-1]["close"])
        return out

    async def _render_visual(
        self,
        spec: VisualSpec,
        prices: dict[str, list[dict[str, Any]]],
        out_dir: Path,
        orientation: str,
    ) -> Path:
        viewport = (1080, 1080) if orientation == "feed" else (1080, 1920)
        raw_path = out_dir / "raw.png"
        out_dir.mkdir(parents=True, exist_ok=True)

        if spec.type == "chart" and spec.symbol and spec.timeframe:
            ohlc = prices.get(spec.symbol, [])
            try:
                render_chart_png(
                    ohlc=ohlc,
                    symbol=spec.symbol,
                    timeframe=spec.timeframe,
                    annotations=spec.annotations,
                    headline=spec.headline,
                    out_path=raw_path,
                    size=viewport,
                )
                return raw_path
            except Exception as exc:
                logger.warning("chart_render_failed fallback_to_headline error={}", exc)

        if spec.type in ("chart", "headline"):
            try:
                await render_card(
                    template="headline_card.html",
                    context={
                        "headline": spec.headline,
                        "subheadline": spec.subheadline,
                        "summary": " · ".join(spec.annotations[:3]) or "",
                        "label": "Forex News",
                        "handle": self._handle,
                        "orientation": orientation,
                    },
                    out_path=raw_path,
                    viewport=viewport,
                )
                return raw_path
            except Exception as exc:
                logger.warning("html_render_failed fallback_to_pillow error={}", exc)

        # Last resort
        render_text_card(
            headline=spec.headline,
            body=spec.subheadline or "",
            out_path=raw_path,
            size=viewport,
        )
        return raw_path

    async def _process_draft(self, draft: PostDraft) -> Post | None:
        try:
            spec = VisualSpec.model_validate(draft.visual_spec)
        except Exception as exc:
            logger.error("draft_visual_spec_invalid id={} error={}", draft.id, exc)
            return None

        post_dir = self._data_dir / "posts" / str(draft.id)
        with session_scope(self._engine) as s:
            prices = self._latest_prices(s)
        last_close = self._last_close_map(prices)

        raw_visual = await self._render_visual(
            spec=spec, prices=prices, out_dir=post_dir, orientation=draft.post_type
        )
        final_path = post_dir / ("feed.jpg" if draft.post_type == "feed" else "story.jpg")
        if draft.post_type == "feed":
            finalize_feed_image(
                src=raw_visual, dst=final_path, logo_path=self._logo_path, handle=self._handle
            )
        else:
            finalize_story_image(
                src=raw_visual, dst=final_path, logo_path=self._logo_path, handle=self._handle
            )

        opener = pick_opener(seed=draft.id)
        caption = finalize_caption(
            opener=opener,
            body=draft.caption_draft,
            hashtags=list(self._hashtags),
            cta=self._cta,
            disclaimer_required=draft.disclaimer_required,
            prices=last_close,
        )

        scheduled = self._sched(draft)
        return Post(
            draft_id=draft.id,
            post_type=draft.post_type,
            caption_final=caption,
            hashtags=list(self._hashtags),
            asset_path=str(final_path),
            visual_type=spec.type,
            scheduled_for=scheduled,
            status="ready",
        )

    async def run_once(self) -> ComposeSummary:
        processed = 0
        failed = 0
        # Snapshot pending drafts
        with session_scope(self._engine) as s:
            drafts = list(
                s.execute(
                    select(PostDraft).where(PostDraft.status == "pending").order_by(PostDraft.id)
                ).scalars()
            )
            # Detach for use outside session
            draft_data = [(d.id, d) for d in drafts]
            for d in drafts:
                s.expunge(d)

        for draft_id, draft in draft_data:
            try:
                post = await self._process_draft(draft)
                if post is None:
                    failed += 1
                    continue
                with session_scope(self._engine) as s:
                    s.add(post)
                    s.flush()
                    s.execute(
                        select(PostDraft).where(PostDraft.id == draft_id)
                    ).scalar_one().status = "consumed"
                processed += 1
            except Exception as exc:
                logger.error("compose_failed draft_id={} error={}", draft_id, exc)
                failed += 1
                with session_scope(self._engine) as s:
                    s.execute(
                        select(PostDraft).where(PostDraft.id == draft_id)
                    ).scalar_one().status = "rejected"

        logger.info("compose_done processed={} failed={}", processed, failed)
        return ComposeSummary(processed=processed, failed=failed)
```

- [ ] **Step 3: Wire `compose` subcommand**

In `src/ig_qt/app.py`:

```python
async def run_compose_once(*, config_path: Path) -> int:
    from datetime import datetime, timedelta, timezone

    from ig_qt.composer.runner import ComposerRunner

    cfg = load_config(config_path)
    log_dir = cfg.paths.data_dir / "logs"
    configure_logging(log_dir=log_dir, level="INFO", json_logs=True)
    engine = build_engine(cfg.paths.data_dir / "ig_qt.db")
    init_schema(engine)

    def _sched_for(d):  # type: ignore[no-untyped-def]
        # Default schedule: feed at next configured hour, story +30min from now.
        now = datetime.now(timezone.utc)
        if d.post_type == "feed":
            return now.replace(
                hour=cfg.schedule.feed_post_hour, minute=0, second=0, microsecond=0
            )
        return now + timedelta(minutes=30)

    runner = ComposerRunner(
        engine=engine,
        data_dir=cfg.paths.data_dir,
        logo_path=Path(cfg.brand.logo_path),
        handle=cfg.brand.handle,
        scheduled_for_factory=_sched_for,
    )
    summary = await runner.run_once()
    logger.info("compose_done processed={} failed={}", summary.processed, summary.failed)
    return 0 if summary.failed == 0 else 1
```

In `__main__.py` add subcommand `compose` and dispatch to `run_compose_once`.

- [ ] **Step 4: Run full suite**

```bash
uv run pytest tests/composer -v
uv run mypy --strict src/ig_qt/composer/
uv run ruff check src/ tests/
```

- [ ] **Step 5: Manual smoke**

```bash
uv run python -m ig_qt collect
uv run python -m ig_qt analyze
uv run python -m ig_qt compose
ls data/posts/
```

Expected: `data/posts/<id>/feed.jpg` exists, ≤8MB, 1080×1080, sRGB.

- [ ] **Step 6: Commit**

```bash
git add src/ig_qt/composer/runner.py src/ig_qt/app.py src/ig_qt/__main__.py tests/composer/test_runner.py
git commit -m "feat(composer): orchestrate draft→post with visual + caption pipeline"
```

---

## M4 Acceptance Criteria

- [ ] All `tests/composer/*` green
- [ ] `mypy --strict src/ig_qt/composer/` clean
- [ ] `ruff check src/ tests/` clean
- [ ] `compose` produces feed image: 1080×1080, sRGB JPEG, ≤8MB
- [ ] `compose` produces story image: 1080×1920, sRGB JPEG, ≤8MB
- [ ] Visual fallback chain verified: kill chart data → headline card; force HTML render error → pillow fallback
- [ ] Caption substitutes `{usdjpy_close}` etc. with real cached prices
- [ ] Disclaimer auto-appended when `disclaimer_required=true`
- [ ] OD-3 resolved: real logo + brand colors in place (or placeholder accepted explicitly)

## M4 Self-Review Notes

- **Three-tier visual fallback** (chart → HTML → Pillow): each tier raises/logs warning; runner catches and tries next. No single failure blocks publishing entirely.
- **Image size cap (8 MB IG hard limit):** post-process iterates JPEG quality 92 → 60 in steps of 10 until under cap. Below 60 it logs error but still saves; publisher then rejects.
- **Resize uses cover (not contain):** crops to fill 1080×1080 / 1080×1920. Visual templates are designed to leave safe padding so center crop works.
- **Caption opener seeded by draft id:** consistent if same draft re-rendered, varied across drafts.
- **`scheduled_for_factory` isolated:** runner doesn't hardcode timing logic. M5 publisher reads `scheduled_for` and applies jitter at execution time.
- **`raw.png` kept on disk:** debug-friendly. If caption looks wrong, you can inspect raw render. M7 hardening can add cleanup cron.
- **VisualSpec.type="recap" not auto-rendered here:** stories.py builds the context, but recap stories are produced by a separate scheduler job (M5 calls `build_market_recap_context` + `render_card("market_recap.html")` directly without going through PostDraft).
