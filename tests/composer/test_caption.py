"""Tests for caption finalizer."""
from __future__ import annotations

from ig_qt.composer.caption import (
    DISCLAIMER,
    finalize_caption,
    pick_opener,
    substitute_placeholders,
)


def test_pick_opener_returns_one_of_pool() -> None:
    op = pick_opener(seed=1)
    assert isinstance(op, str)
    assert len(op) > 0


def test_pick_opener_seed_deterministic() -> None:
    assert pick_opener(seed=42) == pick_opener(seed=42)


def test_substitute_placeholders_replaces_known_keys() -> None:
    text = "EUR/USD close: {eurusd_close}, USD/JPY: {usdjpy_close}"
    result = substitute_placeholders(
        text, prices={"EUR/USD": 1.0865, "USD/JPY": 158.42}
    )
    assert "1.0865" in result
    assert "158.42" in result


def test_substitute_placeholders_strips_unresolved() -> None:
    text = "Today {unknown_key} matters"
    result = substitute_placeholders(text, prices={})
    assert "{unknown_key}" not in result


def test_finalize_caption_appends_disclaimer_when_required() -> None:
    out = finalize_caption(
        opener="Update pasar:",
        body="Fed hawkish, USD strong.",
        hashtags=["#forex", "#fed", "#trading"],
        cta="Follow @x",
        disclaimer_required=True,
        prices={},
    )
    assert DISCLAIMER in out
    assert "Update pasar:" in out
    assert "#forex" in out
    assert "Follow @x" in out


def test_finalize_caption_no_disclaimer_when_not_required() -> None:
    out = finalize_caption(
        opener="Hi",
        body="x",
        hashtags=[],
        cta="",
        disclaimer_required=False,
        prices={},
    )
    assert DISCLAIMER not in out


def test_finalize_caption_truncates_to_ig_limit() -> None:
    body = "x" * 2300
    out = finalize_caption(
        opener="A",
        body=body,
        hashtags=["#a"],
        cta="",
        disclaimer_required=False,
        prices={},
    )
    assert len(out) <= 2200
