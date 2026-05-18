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
