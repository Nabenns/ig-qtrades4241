"""Direct Gemini adapter (generateContent)."""
from __future__ import annotations

import json
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ig_qt.llm.base import LLMResponse


class GeminiProvider:
    name = "gemini"

    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _post(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/models/{model}:generateContent?key={self._api_key}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data

    def _build_payload(
        self, system: str, user: str, temperature: float, max_tokens: int, json_mode: bool
    ) -> dict[str, Any]:
        config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if json_mode:
            config["responseMimeType"] = "application/json"
        return {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": config,
        }

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
        payload = self._build_payload(system, user, temperature, max_output_tokens, json_mode=True)
        data = await self._post(model, payload)
        cand = data["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        usage = data.get("usageMetadata", {})
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        return LLMResponse(
            content=text,
            parsed=parsed,
            model=model,
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
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
        payload = self._build_payload(system, user, temperature, max_output_tokens, json_mode=False)
        data = await self._post(model, payload)
        cand = data["candidates"][0]
        text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            content=text,
            parsed=None,
            model=model,
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
        )
