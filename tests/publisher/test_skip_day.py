"""Tests for deterministic skip-day decision."""
from __future__ import annotations

from datetime import date

from ig_qt.publisher.skip_day import should_skip_day


def test_skip_day_deterministic_per_date() -> None:
    d = date(2026, 5, 17)
    a = should_skip_day(d, probability=0.14, seed="seed-1")
    b = should_skip_day(d, probability=0.14, seed="seed-1")
    assert a == b


def test_skip_day_different_seeds_can_differ() -> None:
    d = date(2026, 5, 17)
    decisions = {should_skip_day(d, probability=0.5, seed=f"seed-{i}") for i in range(50)}
    assert decisions == {True, False}


def test_skip_day_zero_probability_never_skips() -> None:
    d = date(2026, 5, 17)
    assert should_skip_day(d, probability=0.0, seed="x") is False
