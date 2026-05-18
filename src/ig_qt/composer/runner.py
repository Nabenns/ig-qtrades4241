"""Compose pending drafts into ready-to-publish posts."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from ig_qt.analyst.schemas import VisualSpec
from ig_qt.composer.caption import finalize_caption, pick_opener
from ig_qt.composer.chart_renderer import render_chart_png
from ig_qt.composer.html_renderer import build_headline_html, render_card
from ig_qt.composer.image_gen import CloudflareImageGen, ImageGenError
from ig_qt.composer.pillow_fallback import render_text_card
from ig_qt.composer.postprocess import finalize_feed_image, finalize_story_image
from ig_qt.db import session_scope
from ig_qt.models import Post, PostDraft, PriceCache

_DEFAULT_HASHTAGS: tuple[str, ...] = (
    "#forex",
    "#trading",
    "#marketupdate",
    "#usd",
    "#fed",
    "#economy",
    "#macroeconomics",
    "#financialnews",
    "#globalmarkets",
    "#dollar",
    "#euro",
    "#yen",
    "#tradinglife",
    "#chartanalysis",
)
_DEFAULT_CTA = "Komentar pendapatmu di bawah"


@dataclass(frozen=True, slots=True)
class ComposeSummary:
    processed: int
    failed: int


class ComposerRunner:
    def __init__(
        self,
        *,
        engine: Engine,
        data_dir: Path,
        logo_path: Path,
        handle: str,
        scheduled_for_factory: Callable[[PostDraft], Any],
        hashtags: tuple[str, ...] = _DEFAULT_HASHTAGS,
        cta: str = _DEFAULT_CTA,
        image_gen: CloudflareImageGen | None = None,
    ) -> None:
        self._engine = engine
        self._data_dir = data_dir
        self._logo_path = logo_path
        self._handle = handle
        self._sched = scheduled_for_factory
        self._hashtags = hashtags
        self._cta = cta
        self._image_gen = image_gen

    def _latest_prices(self, session: Session) -> dict[str, list[dict[str, Any]]]:
        rows = list(session.execute(select(PriceCache)).scalars())
        latest: dict[str, PriceCache] = {}
        for r in rows:
            cur = latest.get(r.symbol)
            if cur is None or r.fetched_at > cur.fetched_at:
                latest[r.symbol] = r
        return {sym: list(r.ohlc_json) for sym, r in latest.items()}

    def _last_close_map(
        self, prices: dict[str, list[dict[str, Any]]]
    ) -> dict[str, float]:
        out: dict[str, float] = {}
        for sym, ohlc in prices.items():
            if ohlc:
                out[sym] = float(ohlc[-1]["close"])
        return out

    async def _maybe_generate_hero(
        self, spec: VisualSpec, out_dir: Path
    ) -> Path | None:
        """Generate AI hero image if image_gen is enabled and prompt is provided."""
        if self._image_gen is None or not spec.hero_image_prompt:
            return None
        hero_path = out_dir / "hero.png"
        if hero_path.exists():
            return hero_path
        try:
            return await self._image_gen.generate(
                prompt=spec.hero_image_prompt, out_path=hero_path
            )
        except ImageGenError as exc:
            logger.warning("hero_image_failed err={}", exc)
            return None

    async def _render_visual(
        self,
        spec: VisualSpec,
        prices: dict[str, list[dict[str, Any]]],
        out_dir: Path,
        orientation: str,
    ) -> Path:
        viewport = (1080, 1350) if orientation == "feed" else (1080, 1920)
        raw_path = out_dir / "raw.png"
        out_dir.mkdir(parents=True, exist_ok=True)

        if spec.type == "chart" and spec.symbol and spec.timeframe:
            ohlc = prices.get(spec.symbol, [])
            try:
                render_chart_png(
                    ohlc=ohlc,
                    symbol=spec.symbol,
                    timeframe=spec.timeframe,
                    annotations=spec.annotations,
                    headline=spec.headline,
                    out_path=raw_path,
                    size=viewport,
                )
                return raw_path
            except Exception as exc:
                logger.warning("chart_render_failed fallback_to_headline error={}", exc)

        # Build rich context for new templates
        headline_html = build_headline_html(
            headline=spec.headline,
            highlight_phrase=spec.highlight_phrase,
            highlight_color=spec.highlight_color,
        )
        context: dict[str, Any] = {
            "headline": spec.headline,
            "headline_html": headline_html,
            "subheadline": spec.subheadline,
            "summary": " · ".join(spec.annotations[:3]) or "",
            "label": "Forex News",
            "handle": self._handle,
            "orientation": orientation,
            "eyebrow": "Forex News" if orientation == "feed" else "Macro Watch",
            "eyebrow_meta": "Live" if orientation == "feed" else "Today",
            "big_number": spec.big_number,
            "big_number_label": spec.big_number_label,
            "big_number_caption": spec.big_number_caption,
            "stats": [s.model_dump() for s in spec.stats],
            "quote": spec.quote.model_dump() if spec.quote else None,
            "insight": spec.insight.model_dump() if spec.insight else None,
        }

        # Try to generate AI hero image (Cloudflare) — only when prompt exists
        hero_path = await self._maybe_generate_hero(spec, out_dir)

        # Pick template based on visual_spec.type
        # `news_hero` is the CW-style cinematic layout requiring a hero image
        if spec.type == "news_hero" and hero_path is not None:
            try:
                await render_card(
                    template="news_breaking.html",
                    context=context,
                    out_path=raw_path,
                    viewport=viewport,
                    hero_image_path=hero_path,
                )
                return raw_path
            except Exception as exc:
                logger.warning("news_hero_render_failed fallback err={}", exc)

        if spec.type in ("chart", "headline", "big_number", "panel", "news_hero"):
            try:
                await render_card(
                    template="headline_card.html",
                    context=context,
                    out_path=raw_path,
                    viewport=viewport,
                )
                return raw_path
            except Exception as exc:
                logger.warning("html_render_failed fallback_to_pillow error={}", exc)

        render_text_card(
            headline=spec.headline,
            body=spec.subheadline or "",
            out_path=raw_path,
            size=viewport,
        )
        return raw_path

    async def _process_draft(self, draft: PostDraft) -> Post | None:
        try:
            spec = VisualSpec.model_validate(draft.visual_spec)
        except Exception as exc:
            logger.error("draft_visual_spec_invalid id={} error={}", draft.id, exc)
            return None

        post_dir = self._data_dir / "posts" / str(draft.id)
        with session_scope(self._engine) as s:
            prices = self._latest_prices(s)
        last_close = self._last_close_map(prices)

        raw_visual = await self._render_visual(
            spec=spec, prices=prices, out_dir=post_dir, orientation=draft.post_type
        )
        final_path = post_dir / ("feed.jpg" if draft.post_type == "feed" else "story.jpg")
        if draft.post_type == "feed":
            finalize_feed_image(
                src=raw_visual, dst=final_path, logo_path=self._logo_path, handle=self._handle
            )
        else:
            finalize_story_image(
                src=raw_visual, dst=final_path, logo_path=self._logo_path, handle=self._handle
            )

        opener = pick_opener(seed=draft.id)
        caption = finalize_caption(
            opener=opener,
            body=draft.caption_draft,
            hashtags=list(self._hashtags),
            cta=self._cta,
            disclaimer_required=draft.disclaimer_required,
            prices=last_close,
        )

        scheduled = self._sched(draft)
        return Post(
            draft_id=draft.id,
            post_type=draft.post_type,
            caption_final=caption,
            hashtags=list(self._hashtags),
            asset_path=str(final_path),
            visual_type=spec.type,
            scheduled_for=scheduled,
            status="ready",
        )

    async def run_once(self) -> ComposeSummary:
        processed = 0
        failed = 0
        with session_scope(self._engine) as s:
            drafts = list(
                s.execute(
                    select(PostDraft).where(PostDraft.status == "pending").order_by(PostDraft.id)
                ).scalars()
            )
            draft_data = [(d.id, d) for d in drafts]
            for d in drafts:
                s.expunge(d)

        for draft_id, draft in draft_data:
            try:
                post = await self._process_draft(draft)
                if post is None:
                    failed += 1
                    continue
                with session_scope(self._engine) as s:
                    s.add(post)
                    s.flush()
                    target = s.execute(
                        select(PostDraft).where(PostDraft.id == draft_id)
                    ).scalar_one()
                    target.status = "consumed"
                processed += 1
            except Exception as exc:
                logger.error("compose_failed draft_id={} error={}", draft_id, exc)
                failed += 1
                with session_scope(self._engine) as s:
                    target = s.execute(
                        select(PostDraft).where(PostDraft.id == draft_id)
                    ).scalar_one()
                    target.status = "rejected"

        logger.info("compose_done processed={} failed={}", processed, failed)
        return ComposeSummary(processed=processed, failed=failed)
