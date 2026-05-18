"""Tests for image post-processing."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from ig_qt.composer.postprocess import (
    finalize_feed_image,
    finalize_story_image,
)


def _make_test_image(path: Path, size: tuple[int, int]) -> None:
    img = Image.new("RGB", size, (15, 23, 42))
    img.save(path, "PNG")


def test_finalize_feed_resizes_to_1080x1350(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    _make_test_image(src, (2000, 2000))
    logo = tmp_path / "logo.png"
    _make_test_image(logo, (256, 256))
    dst = tmp_path / "out.jpg"
    out = finalize_feed_image(src=src, dst=dst, logo_path=logo, handle="@x")
    img = Image.open(out)
    assert img.size == (1080, 1350)
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
    arr = (np.random.rand(2200, 2200, 3) * 255).astype("uint8")  # noqa: NPY002
    src = tmp_path / "src.png"
    Image.fromarray(arr).save(src, "PNG")
    logo = tmp_path / "logo.png"
    Image.new("RGB", (256, 256), (255, 0, 0)).save(logo, "PNG")
    dst = tmp_path / "out.jpg"
    finalize_feed_image(src=src, dst=dst, logo_path=logo, handle="@x")
    assert dst.stat().st_size < 8 * 1024 * 1024
