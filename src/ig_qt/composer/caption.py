"""Caption finalization: opener variation, placeholder substitution, disclaimer, hashtags, CTA."""
from __future__ import annotations

import random
import re
from collections.abc import Mapping, Sequence

DISCLAIMER = (
    "_*Bukan rekomendasi trading. Lakukan riset sendiri & kelola risiko.*_"
)

_OPENERS: tuple[str, ...] = (
    "Update pasar hari ini:",
    "Yang lagi happening di pasar:",
    "Highlight macro hari ini:",
    "Forex watch:",
    "Market context yang lagi panas:",
    "Recap pasar:",
    "Yang perlu kamu tahu hari ini:",
    "Sorotan trading hari ini:",
    "Macro check:",
    "Hot takes pasar:",
    "Forex briefing:",
    "Konteks pasar terkini:",
    "Update penting buat trader:",
    "Pasar lagi gerak gini:",
    "Fokus market hari ini:",
    "Risk-on atau risk-off?",
    "Daily forex digest:",
    "Pasar bicara apa hari ini?",
    "Setup pasar yang menarik:",
    "Briefing harian forex:",
)

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_]+)\}")

_PLACEHOLDER_TO_SYMBOL: Mapping[str, str] = {
    "eurusd_close": "EUR/USD",
    "gbpusd_close": "GBP/USD",
    "usdjpy_close": "USD/JPY",
    "xauusd_close": "XAU/USD",
    "dxy_close": "DXY",
    "btcusd_close": "BTC/USD",
}


def pick_opener(*, seed: int | None = None) -> str:
    rng = random.Random(seed) if seed is not None else random  # noqa: S311
    return rng.choice(_OPENERS)  # noqa: S311


def substitute_placeholders(text: str, *, prices: Mapping[str, float]) -> str:
    """Replace `{eurusd_close}` style tokens with formatted prices. Strip unresolved."""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).lower()
        symbol = _PLACEHOLDER_TO_SYMBOL.get(key)
        if symbol is None or symbol not in prices:
            return ""
        val = prices[symbol]
        return f"{val:.4f}" if val < 100 else f"{val:.2f}"

    result = _PLACEHOLDER_RE.sub(replace, text)
    return re.sub(r"\s{2,}", " ", result).strip()


def finalize_caption(
    *,
    opener: str,
    body: str,
    hashtags: Sequence[str],
    cta: str,
    disclaimer_required: bool,
    prices: Mapping[str, float],
    max_chars: int = 2200,
) -> str:
    """Assemble final caption respecting IG 2200-char limit."""
    body_filled = substitute_placeholders(body, prices=prices)
    parts: list[str] = [opener, "", body_filled]
    if disclaimer_required:
        parts.extend(["", DISCLAIMER])
    if cta:
        parts.extend(["", cta])
    if hashtags:
        tag_block = " ".join(hashtags[:15])
        parts.extend(["", tag_block])
    full = "\n".join(parts).strip()
    if len(full) > max_chars:
        overflow = len(full) - max_chars
        new_body = body_filled[: max(0, len(body_filled) - overflow - 4)] + "..."
        parts = [opener, "", new_body]
        if disclaimer_required:
            parts.extend(["", DISCLAIMER])
        if cta:
            parts.extend(["", cta])
        if hashtags:
            parts.extend(["", " ".join(hashtags[:15])])
        full = "\n".join(parts).strip()
    return full[:max_chars]
