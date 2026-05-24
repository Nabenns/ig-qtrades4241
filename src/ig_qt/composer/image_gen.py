"""Hero image generation adapters.

Two paths supported:
- `Router9ImageGen` (recommended): routes via 9router's OpenAI-compatible
  /v1/images/generations endpoint. Lets you connect Cloudflare/Fal/Stability/etc
  in 9router dashboard once and use a single API key for everything.
- `CloudflareImageGen`: direct call to Cloudflare Workers AI. Free tier ~10K/day.
  Useful when you don't want to run 9router or want to bypass it.

Both produce a PNG file at the requested path.
"""
from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Style hints to keep generations brand-safe and on-aesthetic.
# IMPORTANT: explicitly forbid all text/typography because Flux can't spell
# reliably and renders garbled words on signs, banners, etc.
_STYLE_SUFFIX = (
    ", cinematic lighting, photorealistic, dramatic atmosphere, dark moody,"
    " 4k high quality, abstract symbolic composition, no readable text,"
    " plain unmarked surfaces, blank facades, no signage, no banners,"
    " no billboards, no street signs, no posters, no documents, no screens,"
    " no books, no labels, no logos, no watermarks"
)

# Substrings that historically cause Flux to render garbled text on signs,
# building facades, banners, etc. We append a "no signage" reminder when any
# of these appear in the user prompt.
_TEXT_PRONE_TOKENS: tuple[str, ...] = (
    "facade",
    "facades",
    "building",
    "buildings",
    "skyline",
    "office",
    "office tower",
    "shop",
    "store",
    "storefront",
    "billboard",
    "banner",
    "newspaper",
    "newspapers",
    "headline",
    "magazine",
    "poster",
    "screen",
    "screens",
    "monitor",
    "tv",
    "billboard",
    "ticker",
    "exchange",
    "chart",
    "infographic",
    "document",
    "letter",
    "envelope",
    "label",
    "logo",
    "sign",
    "signage",
)


def _sanitize_text_prone_prompt(prompt: str) -> str:
    """If the prompt contains tokens that often induce Flux to render garbled text
    (building facades, billboards, newspapers, screens), prepend an extra
    "no readable text" reminder. Cheaper than retry loops.
    """
    lowered = prompt.lower()
    if any(tok in lowered for tok in _TEXT_PRONE_TOKENS):
        return (
            "abstract symbolic interpretation, no readable text or letters anywhere, "
            "blank surfaces, "
            + prompt
        )
    return prompt


class ImageGenError(Exception):
    """Image generation failure."""


@runtime_checkable
class ImageGenerator(Protocol):
    """Protocol for hero image generation backends."""

    name: str

    async def generate(self, *, prompt: str, out_path: Path) -> Path:
        """Generate image from prompt, save to out_path. Returns path on success."""
        ...


def _decode_b64_to_file(b64: str, out_path: Path) -> Path:
    """Helper: decode base64 PNG and save to disk."""
    try:
        png_bytes = base64.b64decode(b64)
    except (ValueError, binascii.Error) as exc:
        raise ImageGenError(f"failed to decode base64 image: {exc}") from exc
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(png_bytes)
    return out_path


class Router9ImageGen:
    """Image gen via 9router OpenAI-compatible /v1/images/generations endpoint.

    Setup: connect Cloudflare (or Fal/Stability/BFL/etc) provider in 9router
    dashboard. Use the model id as shown there, e.g.:
        cf/@cf/black-forest-labs/flux-1-schnell
    """

    name = "router_9_image"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        size: str = "1024x1024",
        timeout: float = 60.0,
    ) -> None:
        self._url = base_url.rstrip("/") + "/images/generations"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._model = model
        self._size = size
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=12),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._url, json=payload, headers=self._headers)
            if resp.status_code >= 400:
                logger.error(
                    "router9_image_http_error status={} body={}",
                    resp.status_code,
                    resp.text[:400],
                )
                resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data

    async def generate(self, *, prompt: str, out_path: Path) -> Path:
        full_prompt = (_sanitize_text_prone_prompt(prompt.strip()) + _STYLE_SUFFIX)[:2000]
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": full_prompt,
            "n": 1,
            "size": self._size,
            "response_format": "b64_json",
        }
        try:
            data = await self._post(payload)
        except Exception as exc:
            raise ImageGenError(f"router_9 image gen failed: {exc}") from exc

        items = data.get("data") or []
        if not items:
            raise ImageGenError(f"router_9 returned no images: {data}")
        first = items[0]
        b64 = first.get("b64_json")
        url = first.get("url")
        if b64:
            _decode_b64_to_file(b64, out_path)
        elif url:
            # Some upstreams return URL instead of base64 — fetch it
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(resp.content)
        else:
            raise ImageGenError(f"router_9 image item has no b64_json/url: {first}")
        logger.info(
            "image_gen_done backend=router_9 model={} path={} prompt_preview={}",
            self._model,
            out_path,
            prompt[:80],
        )
        return out_path


class CloudflareImageGen:
    """Direct Cloudflare Workers AI Flux Schnell adapter.

    Free tier: 10K images/day. Use this when you don't want to run 9router.
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
        full_prompt = _sanitize_text_prone_prompt(prompt.strip()) + _STYLE_SUFFIX
        payload: dict[str, Any] = {
            "prompt": full_prompt[:2000],
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

        _decode_b64_to_file(b64_image, out_path)
        logger.info(
            "image_gen_done backend=cloudflare path={} prompt_preview={}",
            out_path,
            prompt[:80],
        )
        return out_path


def build_image_gen(
    *,
    enabled: bool,
    provider: str,
    # Router9 fields
    router_base_url: str | None = None,
    router_api_key: str | None = None,
    router_model: str | None = None,
    # Cloudflare fields
    cf_account_id: str | None = None,
    cf_api_token: str | None = None,
) -> ImageGenerator | None:
    """Factory: returns adapter based on provider config.

    provider="router_9": uses 9router /v1/images/generations
    provider="cloudflare": direct Cloudflare Workers AI
    """
    if not enabled:
        return None

    if provider == "router_9":
        if not (router_base_url and router_api_key and router_model):
            logger.warning(
                "image_gen_router9_missing_config base_url={} key={} model={}",
                bool(router_base_url),
                bool(router_api_key),
                bool(router_model),
            )
            return None
        return Router9ImageGen(
            base_url=router_base_url, api_key=router_api_key, model=router_model
        )

    if provider == "cloudflare":
        if not (cf_account_id and cf_api_token):
            logger.warning("image_gen_cloudflare_missing_config")
            return None
        return CloudflareImageGen(account_id=cf_account_id, api_token=cf_api_token)

    logger.warning("image_gen_unknown_provider provider={}", provider)
    return None
