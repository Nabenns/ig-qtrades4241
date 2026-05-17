"""Direct OpenAI adapter — same wire format as Router9 (subclass)."""
from __future__ import annotations

from ig_qt.llm.router_9 import Router9Provider


class OpenAIProvider(Router9Provider):
    """OpenAI is OpenAI-compatible by definition; reuse Router9 wire format."""

    name = "openai"
