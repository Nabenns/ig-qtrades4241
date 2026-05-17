"""Provider-agnostic LLM interface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class LLMResponse:
    """Result of an LLM call."""

    content: str
    parsed: dict[str, Any] | None
    model: str
    input_tokens: int
    output_tokens: int


@runtime_checkable
class LLMProvider(Protocol):
    """Provider interface — implemented per backend."""

    name: str

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
        """Run a chat completion that returns a JSON object."""
        ...

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.7,
        max_output_tokens: int = 1500,
    ) -> LLMResponse:
        """Run a plain-text chat completion."""
        ...
