"""Tests for LLM factory."""
from __future__ import annotations

import pytest
from pydantic import SecretStr

from ig_qt.config import LLMConfig
from ig_qt.llm.base import LLMProvider
from ig_qt.llm.factory import build_llm_provider


@pytest.mark.parametrize("provider_name", ["router_9", "openai", "anthropic", "gemini"])
def test_factory_returns_provider_for_each_name(provider_name: str) -> None:
    cfg = LLMConfig(
        provider=provider_name,  # type: ignore[arg-type]
        base_url="https://x",
        api_key=SecretStr("k"),
        ranker_model="r",
        composer_model="c",
    )
    p = build_llm_provider(cfg)
    assert isinstance(p, LLMProvider)


def test_factory_raises_for_unknown() -> None:
    cfg = LLMConfig(
        provider="router_9",
        base_url="https://x",
        api_key=SecretStr("k"),
        ranker_model="r",
        composer_model="c",
    )
    object.__setattr__(cfg, "provider", "bogus")
    with pytest.raises(ValueError, match="unknown llm provider"):
        build_llm_provider(cfg)
