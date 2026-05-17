"""Direct Anthropic adapter (Messages API)."""
from __future__ import annotations

import json
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.llm.base import LLMResponse


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
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
                f"{self._base_url}/messages",
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
            "system": system,
            "messages": [{"role": "user", "content": user + "\n\nReply with JSON only."}],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        data = await self._post(payload)
        text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        return LLMResponse(
            content=text,
            parsed=parsed,
            model=model,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
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
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        data = await self._post(payload)
        text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        return LLMResponse(
            content=text,
            parsed=None,
            model=model,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
        )
