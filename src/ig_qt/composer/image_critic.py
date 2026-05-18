"""Vision-based image critic using Mistral Small 3.1 via 9router.

After hero image generation, this critic scores the image (0.0-1.0) on
suitability as a forex/finance Instagram hero background. Returns score
+ feedback so the composer loop can decide: accept, retry with tweaked
prompt, or accept best-so-far.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

_CRITIC_SYSTEM = (
    "You are an art director reviewing AI-generated hero images for a forex/"
    "finance Instagram account (qtradesedu, Indonesian audience). The image will "
    "be used as a CINEMATIC FULL-BLEED BACKGROUND with a headline overlaid on top.\n\n"
    "Score the image 0.0-1.0 on these criteria:\n"
    "- 0.9+ : excellent. Cinematic, dramatic, photorealistic, clear subject, "
    "room for headline overlay (dark/contrasty bottom area), professional finance"
    "/news vibe\n"
    "- 0.7-0.9 : good. Subject clear, decent composition, minor flaws (slight "
    "clutter, unclear focal, or partial flatness)\n"
    "- 0.5-0.7 : okay. Recognizable subject but flat lighting, weak composition, "
    "or generic look\n"
    "- below 0.5 : reject. Wrong subject, AI artifacts (extra fingers, distorted "
    "text), bad composition, too bright/no overlay space, off-brand\n\n"
    'Reply STRICTLY with JSON: {"score": 0.0-1.0, "issues": "1-line issue summary'
    ' or none", "tweak_hint": "1-line suggestion to improve regen prompt or '
    'accept as-is"}. No markdown fences. No commentary.'
)


@dataclass(frozen=True, slots=True)
class CriticVerdict:
    score: float
    issues: str
    tweak_hint: str


class ImageCritic:
    """Score generated images via 9router multimodal LLM (Mistral 3.1 default)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str = "cf/@cf/mistralai/mistral-small-3.1-24b-instruct",
        timeout: float = 60.0,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._model = model
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(min=2, max=8),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._url, json=payload, headers=self._headers)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data

    async def score(
        self, *, image_path: Path, original_prompt: str
    ) -> CriticVerdict | None:
        """Score image. Returns None on transport error (caller decides default)."""
        if not image_path.exists():
            return None
        try:
            img_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        except OSError as exc:
            logger.warning("critic_read_fail path={} err={}", image_path, exc)
            return None

        user_text = (
            f"Generated for prompt: {original_prompt[:300]}\n\n"
            "Review the image. Return JSON only."
        )
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": _CRITIC_SYSTEM,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                        },
                        {"type": "text", "text": user_text},
                    ],
                },
            ],
            "max_tokens": 300,
            "temperature": 0.2,
            "stream": False,
        }

        try:
            data = await self._post(payload)
        except Exception as exc:
            logger.warning("critic_call_failed err={}", exc)
            return None

        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            logger.warning("critic_unexpected_response shape={}", str(data)[:300])
            return None

        verdict = _parse_critic_json(content)
        if verdict is None:
            logger.warning("critic_unparseable preview={}", content[:200])
            return None
        logger.info(
            "critic_verdict score={} issues={} hint={}",
            verdict.score,
            verdict.issues,
            verdict.tweak_hint,
        )
        return verdict


_JSON_BLOCK_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _parse_critic_json(text: str) -> CriticVerdict | None:
    """Extract first JSON object from text, validate fields."""
    text = text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[:-3].strip()
    candidates: list[str] = [text]
    # Also try regex match for embedded JSON
    match = _JSON_BLOCK_RE.search(text)
    if match:
        candidates.append(match.group(0))

    for cand in candidates:
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        score_raw = obj.get("score")
        try:
            score = float(score_raw) if score_raw is not None else 0.0
        except (TypeError, ValueError):
            continue
        score = max(0.0, min(1.0, score))
        issues = str(obj.get("issues") or "").strip()[:200]
        tweak = str(obj.get("tweak_hint") or "").strip()[:240]
        return CriticVerdict(
            score=score, issues=issues or "none", tweak_hint=tweak or "accept as-is"
        )
    return None


def build_image_critic(
    *, enabled: bool, base_url: str | None, api_key: str | None
) -> ImageCritic | None:
    """Factory. Returns None when disabled or creds missing."""
    if not enabled or not base_url or not api_key:
        return None
    return ImageCritic(base_url=base_url, api_key=api_key)
