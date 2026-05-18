"""Last-resort renderer using only Pillow (no Playwright/mplfinance)."""
from __future__ import annotations

import textwrap
from pathlib import Path

from loguru import logger
from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
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
