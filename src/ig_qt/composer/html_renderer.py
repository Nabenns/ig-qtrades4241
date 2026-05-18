"""Render HTML templates to PNG via Playwright."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape
from loguru import logger

from ig_qt.collector.playwright_runner import browser_session

_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
_LOGO_PATH = Path(__file__).resolve().parents[3] / "assets" / "logo.png"


def _build_env() -> Environment:
    return Environment(
        loader=ChoiceLoader([FileSystemLoader(str(_TEMPLATES_DIR))]),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _logo_data_uri() -> str:
    """Encode logo PNG as base64 data URI so Chromium can load it from set_content
    (file:// URLs are blocked when document has no origin).
    """
    if not _LOGO_PATH.exists():
        return ""
    raw = _LOGO_PATH.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


async def render_card(
    *,
    template: str,
    context: dict[str, Any],
    out_path: Path,
    viewport: tuple[int, int],
) -> Path:
    """Render Jinja template, screenshot via headless Chromium, save PNG."""
    env = _build_env()
    ctx = {**context, "logo_url": _logo_data_uri()}
    html = env.get_template(template).render(**ctx)

    async with browser_session() as browser_ctx:
        page = await browser_ctx.new_page()
        await page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
        await page.set_content(html, wait_until="networkidle", timeout=45_000)
        try:
            await page.evaluate("document.fonts.ready")
        except Exception as exc:
            logger.debug("html_render_font_wait_skip err={}", exc)
        # Extra wait for Tailwind CDN to inject computed styles
        await page.wait_for_timeout(800)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(out_path), full_page=False, type="png")
    logger.info("html_render_done template={} out={}", template, out_path)
    return out_path
