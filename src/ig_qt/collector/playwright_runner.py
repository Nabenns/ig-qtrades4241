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
    rng = random.Random(seed) if seed is not None else random  # noqa: S311
    return rng.choice(_UA_POOL)  # noqa: S311


@asynccontextmanager
async def browser_session(
    *,
    timezone_id: str = "Asia/Jakarta",
    locale: str = "en-US",
    device_scale_factor: float = 1.0,
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
            device_scale_factor=device_scale_factor,
        )
        try:
            yield ctx
        finally:
            await ctx.close()
            await browser.close()
            logger.debug("playwright_closed")
