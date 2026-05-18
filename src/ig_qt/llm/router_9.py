"""9router adapter (assumes OpenAI-compatible /v1/chat/completions)."""
from __future__ import annotations

import json
from typing import Any

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.llm.base import LLMResponse


class Router9Provider:
    """OpenAI-compatible adapter for 9router."""

    name = "router_9"

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=self._headers,
            )
            if resp.status_code >= 400:
                logger.error(
                    "router9_http_error status={} body={}",
                    resp.status_code,
                    resp.text[:600],
                )
                resp.raise_for_status()
            try:
                data: dict[str, Any] = resp.json()
            except (ValueError, json.JSONDecodeError) as exc:
                logger.error(
                    "router9_invalid_json status={} body={}",
                    resp.status_code,
                    resp.text[:600],
                )
                raise ValueError(f"9router returned non-JSON: {exc}") from exc
            return data

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.4,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        data = await self._post(payload)
        try:
            choice = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error(
                "router9_unexpected_response shape={}",
                str(data)[:600],
            )
            raise ValueError(f"unexpected 9router response: {exc}") from exc
        if not choice or not choice.strip():
            logger.warning(
                "router9_empty_content model={} full_response={}",
                model,
                str(data)[:600],
            )
        usage = data.get("usage", {})
        # Strip markdown code fences if present
        cleaned = _strip_code_fence(choice or "")
        try:
            parsed = json.loads(cleaned) if cleaned else None
        except json.JSONDecodeError:
            logger.warning(
                "router9_non_json_content model={} preview={}",
                model,
                cleaned[:300],
            )
            parsed = None
        return LLMResponse(
            content=choice or "",
            parsed=parsed,
            model=model,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.7,
        max_output_tokens: int = 1500,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "stream": False,
        }
        data = await self._post(payload)
        try:
            choice = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("router9_unexpected_response shape={}", str(data)[:600])
            raise ValueError(f"unexpected 9router response: {exc}") from exc
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice or "",
            parsed=None,
            model=model,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )


def _strip_code_fence(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrapping if present."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    # Remove opening fence (```json or ```)
    first_newline = text.find("\n")
    if first_newline == -1:
        return text
    inner = text[first_newline + 1 :]
    if inner.endswith("```"):
        inner = inner[:-3]
    return inner.strip()
