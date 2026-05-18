"""Tests for Playwright runner helpers."""
from __future__ import annotations

from ig_qt.collector.playwright_runner import pick_user_agent


def test_pick_user_agent_returns_one_of_pool() -> None:
    ua = pick_user_agent()
    assert "Mozilla" in ua
    assert any(name in ua for name in ("Chrome", "Safari", "Firefox"))


def test_pick_user_agent_with_seed_is_deterministic() -> None:
    a = pick_user_agent(seed=1)
    b = pick_user_agent(seed=1)
    assert a == b
