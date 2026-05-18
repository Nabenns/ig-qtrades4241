"""Final image post-processing: resize, sRGB JPEG with size cap.

Note: watermarking (logo + handle) is now done at HTML render stage to avoid
duplication. Postprocess only normalizes size and converts to sRGB JPEG.
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger
from PIL import Image
from PIL.Image import Resampling

_MAX_BYTES = 8 * 1024 * 1024


def _open_rgb(src: Path) -> Image.Image:
    img: Image.Image = Image.open(src)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _resize_cover(img: Image.Image, target: tuple[int, int]) -> Image.Image:
    """Resize covering target box (no letterboxing, may crop)."""
    tw, th = target
    sw, sh = img.size
    scale = max(tw / sw, th / sh)
    new_w, new_h = int(sw * scale), int(sh * scale)
    img = img.resize((new_w, new_h), Resampling.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return img.crop((left, top, left + tw, top + th))


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
    """Resize to 1080x1350 (4:5 portrait) and save as sRGB JPEG.

    `logo_path` and `handle` are accepted for backward compatibility but no
    longer used (HTML template now embeds logo + handle directly).
    """
    del logo_path, handle  # intentionally unused — branding handled in HTML
    img = _open_rgb(src)
    img = _resize_cover(img, (1080, 1350))
    _save_jpeg_capped(img, dst)
    return dst


def finalize_story_image(
    *, src: Path, dst: Path, logo_path: Path, handle: str
) -> Path:
    """Resize to 1080x1920 and save as sRGB JPEG."""
    del logo_path, handle
    img = _open_rgb(src)
    img = _resize_cover(img, (1080, 1920))
    _save_jpeg_capped(img, dst)
    return dst
