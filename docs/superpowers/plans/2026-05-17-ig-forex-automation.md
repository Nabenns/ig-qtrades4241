# IG Forex Automation Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully-automated Instagram content system for a forex/finance account that collects market news + prices + economic events, generates captions and visuals via LLM, and posts 1 feed/day + 2-3 stories/day to Instagram via instagrapi without per-post human review.

**Architecture:** Linear pipeline (collector → analyst → composer → publisher) as a single Python service backed by SQLite, orchestrated by APScheduler with persistent jobstore. LLM access is provider-agnostic via a Protocol-based factory. Anti-ban tactics layered into the publisher (session persistence, jitter, pre-warmup, rate limits, kill switch, pause-on-challenge).

**Tech Stack:** Python 3.12, uv, SQLAlchemy + SQLite, APScheduler, instagrapi, Playwright, mplfinance, Jinja2, Pillow, Loguru, FastAPI (mini health endpoint), Pydantic Settings, pytest. Deployed as a single Docker container on a VPS.

**Spec:** [`docs/superpowers/specs/2026-05-17-ig-forex-automation-design.md`](../specs/2026-05-17-ig-forex-automation-design.md)

---

## Milestone Index

Each milestone is its own file under `docs/superpowers/plans/ig-qt/`. Execute milestones strictly in order — each one builds on the previous milestone's foundation.

| # | Milestone | Path | Status |
|---|---|---|---|
| M1 | Foundation (scaffold, config, DB, LLM factory, notifier) | [`ig-qt/M1-foundation.md`](ig-qt/M1-foundation.md) | ⏳ |
| M2 | Collector (NewsAPI, GNews, Twelve Data, Forex Factory Playwright, dedup) | [`ig-qt/M2-collector.md`](ig-qt/M2-collector.md) | ⏳ |
| M3 | Analyst (two-stage prompting, evergreen fallback) | [`ig-qt/M3-analyst.md`](ig-qt/M3-analyst.md) | ⏳ |
| M4 | Composer (mplfinance chart, HTML+Playwright cards, post-process) | [`ig-qt/M4-composer.md`](ig-qt/M4-composer.md) | ⏳ |
| M5 | Publisher + Scheduler (instagrapi session, anti-ban, APScheduler) | [`ig-qt/M5-publisher-scheduler.md`](ig-qt/M5-publisher-scheduler.md) | ⏳ |
| M6 | Deploy + Observability (Dockerfile, first-time login, health, backup) | [`ig-qt/M6-deploy-observability.md`](ig-qt/M6-deploy-observability.md) | ⏳ |
| M7 | Hardening (warm-up, prompt v2, monitoring tweaks) | [`ig-qt/M7-hardening.md`](ig-qt/M7-hardening.md) | ⏳ |

## Cross-Milestone Conventions

These rules apply to **every** task in **every** milestone. Don't restate them per task — they're assumed.

- **Type hints required.** No implicit `Any`. Use `from __future__ import annotations` at top of every file.
- **Strict mypy.** `mypy --strict src/` must pass at the end of each milestone.
- **Pydantic for config + LLM structured output.** Never hand-parse JSON from LLM.
- **All file paths absolute or relative to repo root.** Never `../../`.
- **Logging via Loguru `from loguru import logger`.** No `print`. No stdlib `logging`.
- **DB access via SQLAlchemy session context manager.** `with Session(engine) as s:` — never global session.
- **Tests via pytest.** Each module has a sibling test file under `tests/`. Coverage target ≥80% per milestone.
- **Frequent commits.** One logical change = one commit. Conventional commits (`feat(scope):`, `fix(scope):`, `chore(scope):`, `test(scope):`, `docs(scope):`).
- **Run `uv run mypy --strict src/` and `uv run pytest` before every commit.** If either fails, fix before committing.
- **Secrets via `.env` only.** Never commit. `.env.example` template stays in sync.
- **No hardcoded provider names.** Always go through factory (`build_llm_provider(config)`).
- **Error handling explicit.** Result types where possible; exceptions for truly exceptional flow only.

## Open Decisions Tracked

These are unresolved at plan-writing time. Each task that depends on them includes a `**Depends on:**` note pointing here.

| ID | Decision | Default in plan | Resolve before |
|---|---|---|---|
| OD-1 | 9router exposes OpenAI-compatible API? | Plan includes `Router9Provider` adapter assuming OpenAI-compatible. Fallback paths for direct OpenAI/Anthropic/Gemini also included. | M3 Task 3.5 |
| OD-2 | IG account: brand new or existing? | Plan assumes new account → M7 includes warm-up phase (1-2 weeks manual posting) before bot activation. | M7 Task 7.1 |
| OD-3 | Brand assets (logo, color, font) ready? | M4 Task 4.1 includes "prepare brand assets" — placeholder logo + brand vars in `config.yaml`. Easy to swap later. | M4 Task 4.1 |
| OD-4 | Telegram bot: reuse Lapakflow's or new bot? | Plan assumes new bot (`TELEGRAM_BOT_TOKEN` separate). Override = change env var. | M1 Task 1.7 |

## Scope Summary

**In scope (this plan):**
- Single IG account
- Feed posts (single image) + Stories
- Forex / finance / macro content (Indonesian language captions, English technical terms)
- Free-tier data sources only (NewsAPI, GNews, Twelve Data, Forex Factory scrape, yfinance backup)
- LLM provider abstraction (9router default, OpenAI/Anthropic/Gemini fallback)
- Single VPS Docker deployment
- Telegram alerts + UptimeRobot health check

**Out of scope (deferred to future plans):**
- Multi-account support
- Reels (video) generation
- Auto-reply DM/comments
- Carousel posts
- Paid API tiers
- Web admin dashboard
