"""Tests for pre-publish warmup."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from ig_qt.publisher.warmup import simulate_pre_publish_activity


class _FakeClient:
    def __init__(self) -> None:
        self.warmup_calls = 0

    def warmup(self) -> None:
        self.warmup_calls += 1


@pytest.mark.asyncio
async def test_warmup_runs_at_least_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    fake = _FakeClient()
    await simulate_pre_publish_activity(fake, sleep_min=0.0, sleep_max=0.0, seed=1)
    assert fake.warmup_calls >= 1
    # Even with zero sleeps, asyncio.sleep(0) yields control — counted in our patch
    _ = sleeps  # used implicitly

    # When seed makes sleep_max > 0, ensure non-zero sleeps occur
    fake2 = _FakeClient()
    sleeps2: list[float] = []

    async def fake_sleep2(seconds: float) -> None:
        sleeps2.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep2)
    await simulate_pre_publish_activity(fake2, sleep_min=8.0, sleep_max=15.0, seed=1)
    assert any(s > 0 for s in sleeps2)
    assert fake2.warmup_calls >= 1
