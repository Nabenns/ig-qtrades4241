"""End-to-end analyst pipeline."""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import Engine, desc, select
from sqlalchemy.orm import Session

from ig_qt.analyst.angle_generator import generate_angle
from ig_qt.analyst.evergreen import pick_evergreen_draft
from ig_qt.analyst.ranker import run_ranker
from ig_qt.analyst.schemas import AngleDraft, RankerOutput, VisualSpec
from ig_qt.db import session_scope
from ig_qt.llm.base import LLMProvider
from ig_qt.models import Event, EvergreenDraft, PostDraft, PostedTopic, PriceCache, RawNews


@dataclass(frozen=True, slots=True)
class AnalystSummary:
    feed_drafts: int
    story_drafts: int
    evergreen_used: bool
    rejected_low_confidence: int


class AnalystRunner:
    def __init__(
        self,
        *,
        engine: Engine,
        provider: LLMProvider,
        ranker_model: str,
        composer_model: str,
        story_count: int = 3,
        confidence_threshold: float = 0.6,
        prompt_version: str = "ranker.v1+composer.v1",
    ) -> None:
        self._engine = engine
        self._provider = provider
        self._ranker_model = ranker_model
        self._composer_model = composer_model
        self._story_count = story_count
        self._threshold = confidence_threshold
        self._prompt_version = prompt_version

    def _load_news(self, session: Session, since: datetime) -> Sequence[RawNews]:
        return list(
            session.execute(
                select(RawNews)
                .where(RawNews.published_at >= since)
                .order_by(desc(RawNews.published_at))
                .limit(30)
            ).scalars()
        )

    def _load_events(self, session: Session, until: datetime) -> Sequence[Event]:
        return list(
            session.execute(
                select(Event)
                .where(Event.event_time <= until, Event.impact.in_(["high", "medium"]))
                .order_by(Event.event_time)
                .limit(20)
            ).scalars()
        )

    def _load_prices(self, session: Session) -> Sequence[Any]:
        rows = list(session.execute(select(PriceCache)).scalars())
        latest: dict[str, PriceCache] = {}
        for r in rows:
            cur = latest.get(r.symbol)
            if cur is None or r.fetched_at > cur.fetched_at:
                latest[r.symbol] = r
        # Build proxy objects with .symbol and .ohlc attrs (PriceCache has ohlc_json)
        return [_PriceProxy(symbol=p.symbol, ohlc=list(p.ohlc_json)) for p in latest.values()]

    def _load_posted_topics(self, session: Session, days: int = 7) -> Sequence[str]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        return list(
            session.execute(
                select(PostedTopic.topic_tag).where(PostedTopic.last_posted_at >= cutoff)
            ).scalars()
        )

    def _serialize_payload_for_id(
        self, news: Sequence[RawNews], events: Sequence[Event], rid: int
    ) -> str:
        for n in news:
            if n.id == rid:
                return json.dumps(
                    {
                        "type": "news",
                        "title": n.title,
                        "summary": n.summary,
                        "url": n.url,
                        "published_at": (
                            n.published_at.isoformat() if n.published_at else None
                        ),
                        "source": n.source,
                    },
                    ensure_ascii=False,
                )
        for e in events:
            if e.id == rid:
                return json.dumps(
                    {
                        "type": "event",
                        "name": e.name,
                        "currency": e.currency,
                        "impact": e.impact,
                        "forecast": e.forecast,
                        "previous": e.previous,
                        "event_time": e.event_time.isoformat(),
                    },
                    ensure_ascii=False,
                )
        raise KeyError(f"id {rid} not found in news or events")

    def _persist_draft(
        self,
        session: Session,
        draft: AngleDraft,
        source_news_ids: list[int],
    ) -> None:
        session.add(
            PostDraft(
                post_type=draft.post_type,
                source_news_ids=source_news_ids,
                topic_tag=draft.topic_tag,
                angle=draft.angle,
                key_points=list(draft.key_points),
                caption_draft=draft.caption_draft,
                visual_spec=draft.visual_spec.model_dump(),
                dynamic_hashtags=list(draft.dynamic_hashtags),
                disclaimer_required=draft.disclaimer_required,
                confidence=draft.confidence,
                llm_provider=self._provider.name,
                llm_model=self._composer_model,
                prompt_version=self._prompt_version,
                status="pending",
            )
        )

    def _persist_evergreen_as_draft(self, session: Session, ev: EvergreenDraft) -> None:
        spec = VisualSpec.model_validate(ev.visual_spec)
        session.add(
            PostDraft(
                post_type="feed",
                source_news_ids=[],
                topic_tag=f"evergreen_{ev.topic_tag}",
                angle=ev.angle,
                key_points=list(ev.key_points),
                caption_draft=ev.caption_draft,
                visual_spec=spec.model_dump(),
                disclaimer_required=ev.disclaimer_required,
                confidence=0.7,
                llm_provider="evergreen",
                llm_model="cached",
                prompt_version="evergreen.v1",
                status="pending",
            )
        )

    async def run_once(self, *, today: datetime) -> AnalystSummary:
        since = today - timedelta(hours=24)
        until = today + timedelta(hours=24)

        with session_scope(self._engine) as s:
            news = self._load_news(s, since)
            events = self._load_events(s, until)
            prices = self._load_prices(s)
            posted_topics = self._load_posted_topics(s)
            for n in news:
                s.expunge(n)
            for e in events:
                s.expunge(e)

        if not news and not events:
            logger.warning("analyst_no_inputs falling back to evergreen")
            return await self._fallback_evergreen()

        rank: RankerOutput = await run_ranker(
            provider=self._provider,
            model=self._ranker_model,
            today=today,
            news=news,
            events=events,
            prices=prices,
            posted_topics=posted_topics,
        )
        if not rank.ranked:
            return await self._fallback_evergreen()

        ranked_sorted = sorted(rank.ranked, key=lambda r: r.score, reverse=True)
        feed_pick = ranked_sorted[0]
        story_picks = ranked_sorted[1 : 1 + self._story_count]

        feed_drafts = 0
        story_drafts = 0
        rejected = 0
        evergreen_used = False

        with session_scope(self._engine) as s:
            payload = self._serialize_payload_for_id(news, events, feed_pick.id)
            try:
                feed_draft = await generate_angle(
                    provider=self._provider,
                    model=self._composer_model,
                    post_type="feed",
                    selected_payload=payload,
                    prices=prices,
                    posted_topics=posted_topics,
                )
                if feed_draft.confidence >= self._threshold:
                    self._persist_draft(s, feed_draft, [feed_pick.id])
                    feed_drafts = 1
                else:
                    rejected += 1
                    ev = pick_evergreen_draft(s)
                    if ev is not None:
                        self._persist_evergreen_as_draft(s, ev)
                        evergreen_used = True
                        feed_drafts = 1
            except Exception as exc:
                logger.warning("analyst_feed_gen_failed error={}", exc)
                ev = pick_evergreen_draft(s)
                if ev is not None:
                    self._persist_evergreen_as_draft(s, ev)
                    evergreen_used = True
                    feed_drafts = 1

            for pick in story_picks:
                try:
                    payload = self._serialize_payload_for_id(news, events, pick.id)
                    story_draft = await generate_angle(
                        provider=self._provider,
                        model=self._composer_model,
                        post_type="story",
                        selected_payload=payload,
                        prices=prices,
                        posted_topics=posted_topics,
                    )
                    if story_draft.confidence >= self._threshold:
                        self._persist_draft(s, story_draft, [pick.id])
                        story_drafts += 1
                    else:
                        rejected += 1
                except Exception as exc:
                    logger.warning("analyst_story_gen_failed error={}", exc)

        return AnalystSummary(
            feed_drafts=feed_drafts,
            story_drafts=story_drafts,
            evergreen_used=evergreen_used,
            rejected_low_confidence=rejected,
        )

    async def _fallback_evergreen(self) -> AnalystSummary:
        with session_scope(self._engine) as s:
            ev = pick_evergreen_draft(s)
            if ev is None:
                logger.error("analyst_dry_day_no_evergreen")
                return AnalystSummary(0, 0, False, 0)
            self._persist_evergreen_as_draft(s, ev)
        return AnalystSummary(
            feed_drafts=1, story_drafts=0, evergreen_used=True, rejected_low_confidence=0
        )


@dataclass(frozen=True, slots=True)
class _PriceProxy:
    symbol: str
    ohlc: list[dict[str, Any]]
