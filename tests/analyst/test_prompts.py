"""Tests for prompt loader."""
from __future__ import annotations

from ig_qt.analyst.prompts.loader import load_prompt


def test_load_ranker_prompt() -> None:
    p = load_prompt("ranker.v1")
    assert "JSON" in p.system
    assert "{news_lines}" in p.user_template
    rendered = p.render_user(
        today="2026-05-17",
        posted_topics="-",
        news_lines="1 | newsapi | 12:00 | Fed Holds | summary",
        events_lines="-",
        prices_lines="-",
    )
    assert "Fed Holds" in rendered


def test_load_composer_prompt() -> None:
    p = load_prompt("composer.v1")
    assert "Indonesian" in p.system
    assert "{selected_payload}" in p.user_template
