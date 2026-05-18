"""Final image post-processing: resize, watermark, sRGB JPEG with size cap."""
from __future__ import annotations

from pathlib import Path

from loguru import logger
from PIL import Image, ImageDraw, ImageFont
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


def _paste_logo(canvas: Image.Image, logo_path: Path, *, handle: str) -> Image.Image:
    if not logo_path.exists():
        logger.warning("postprocess_logo_missing path={}", logo_path)
        return canvas
    logo = Image.open(logo_path).convert("RGBA")
    logo_size = 96
    logo = logo.resize((logo_size, logo_size), Resampling.LANCZOS)
    x = canvas.width - logo_size - 56
    y = canvas.height - logo_size - 56
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.paste(logo, (x, y), logo)
    draw = ImageDraw.Draw(canvas_rgba)
    try:
        font: ImageFont.ImageFont | ImageFont.FreeTypeFont = ImageFont.truetype(
            "DejaVuSans.ttf", 24
        )
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
    img = _resize_cover(img, (1080, 1350))
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
