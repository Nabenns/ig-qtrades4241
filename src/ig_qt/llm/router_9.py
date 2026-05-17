"""9router adapter (assumes OpenAI-compatible /v1/chat/completions)."""
from __future__ import annotations

import json
from typing import Any

import httpx
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
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
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
        }
        data = await self._post(payload)
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        try:
            parsed = json.loads(choice)
        except json.JSONDecodeError:
            parsed = None
        return LLMResponse(
            content=choice,
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
        }
        data = await self._post(payload)
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice,
            parsed=None,
            model=model,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )
