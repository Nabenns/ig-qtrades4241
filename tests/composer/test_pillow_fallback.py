"""Tests for Pillow fallback renderer."""
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
