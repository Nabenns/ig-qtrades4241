"""Build a concrete LLMProvider from LLMConfig."""
from __future__ import annotations

from ig_qt.config import LLMConfig
from ig_qt.llm.anthropic_provider import AnthropicProvider
from ig_qt.llm.base import LLMProvider
from ig_qt.llm.gemini_provider import GeminiProvider
from ig_qt.llm.openai_provider import OpenAIProvider
from ig_qt.llm.router_9 import Router9Provider


def build_llm_provider(cfg: LLMConfig) -> LLMProvider:
    """Resolve config.provider → concrete adapter."""
    api_key = cfg.api_key.get_secret_value()
    timeout = float(cfg.request_timeout_seconds)

    if cfg.provider == "router_9":
        return Router9Provider(base_url=cfg.base_url, api_key=api_key, timeout=timeout)
    if cfg.provider == "openai":
        return OpenAIProvider(base_url=cfg.base_url, api_key=api_key, timeout=timeout)
    if cfg.provider == "anthropic":
        return AnthropicProvider(base_url=cfg.base_url, api_key=api_key, timeout=timeout)
    if cfg.provider == "gemini":
        return GeminiProvider(base_url=cfg.base_url, api_key=api_key, timeout=timeout)
    raise ValueError(f"unknown llm provider: {cfg.provider}")
