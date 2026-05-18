"""Cloudflare Workers AI adapter for hero image generation.

Generates dramatic background images via Flux Schnell. Free tier supports
~10K images/day. Output is base64-encoded PNG saved to disk.
"""
from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Negative-style style hints to keep generations brand-safe and on-aesthetic
_STYLE_SUFFIX = (
    ", cinematic lighting, photorealistic, dramatic atmosphere, dark moody,"
    " 4k high quality, no text, no watermark, no logo"
)


class ImageGenError(Exception):
    """Image generation failure."""


class CloudflareImageGen:
    """Cloudflare Workers AI Flux Schnell adapter.

    Free tier: 10K images/day. No persistent state.
    """

    name = "cloudflare_flux_schnell"

    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
        timeout: float = 60.0,
        steps: int = 4,
    ) -> None:
        self._account_id = account_id
        self._api_token = api_token
        self._timeout = timeout
        self._steps = steps
        self._url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
            f"/ai/run/@cf/black-forest-labs/flux-1-schnell"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=12),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_token}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code >= 400:
                logger.error(
                    "cloudflare_image_http_error status={} body={}",
                    resp.status_code,
                    resp.text[:400],
                )
                resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data

    async def generate(self, *, prompt: str, out_path: Path) -> Path:
        """Generate image from prompt, save to out_path. Returns path on success."""
        full_prompt = prompt.strip() + _STYLE_SUFFIX
        payload: dict[str, Any] = {
            "prompt": full_prompt[:2000],  # CF prompt limit
            "steps": self._steps,
        }
        try:
            data = await self._post(payload)
        except Exception as exc:
            raise ImageGenError(f"cloudflare api failed: {exc}") from exc

        if not data.get("success"):
            errors = data.get("errors", [])
            raise ImageGenError(f"cloudflare returned errors: {errors}")

        result = data.get("result") or {}
        b64_image = result.get("image")
        if not b64_image or not isinstance(b64_image, str):
            raise ImageGenError(f"cloudflare missing image in response: {data}")

        try:
            png_bytes = base64.b64decode(b64_image)
        except (ValueError, binascii.Error) as exc:
            raise ImageGenError(f"failed to decode base64 image: {exc}") from exc

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(png_bytes)
        logger.info(
            "image_gen_done path={} bytes={} prompt_preview={}",
            out_path,
            len(png_bytes),
            prompt[:80],
        )
        return out_path


def build_image_gen(
    *, enabled: bool, account_id: str | None, api_token: str | None
) -> CloudflareImageGen | None:
    """Factory: returns adapter when enabled and creds present, else None."""
    if not enabled or not account_id or not api_token:
        return None
    return CloudflareImageGen(account_id=account_id, api_token=api_token)
