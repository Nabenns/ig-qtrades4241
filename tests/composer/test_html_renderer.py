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
    # Renders at 2x device scale factor by default
    assert img.size == (2160, 2160)


@pytest.mark.asyncio
async def test_render_event_card_with_two_events(tmp_path: Path) -> None:
    out = tmp_path / "event.png"
    await render_card(
        template="event_card.html",
        context={
            "headline": "Event Hari Ini",
            "subheadline": "2 high-impact events",
            "events": [
                {
                    "time": "12:30",
                    "currency": "USD",
                    "name": "CPI m/m",
                    "impact": "high",
                    "forecast": "0.3%",
                    "previous": "0.4%",
                },
                {
                    "time": "20:00",
                    "currency": "EUR",
                    "name": "ECB Rate",
                    "impact": "high",
                    "forecast": "4.50%",
                    "previous": "4.50%",
                },
            ],
            "handle": "@x",
            "orientation": "story",
        },
        out_path=out,
        viewport=(1080, 1920),
    )
    img = Image.open(out)
    assert img.size == (2160, 3840)
