"""Deterministic skip-day decision: ~14% chance per day, stable per (date, seed)."""
from __future__ import annotations

import hashlib
from datetime import date


def should_skip_day(d: date, *, probability: float, seed: str) -> bool:
    if probability <= 0:
        return False
    if probability >= 1:
        return True
    key = f"{seed}|{d.isoformat()}".encode()
    digest = hashlib.sha256(key).digest()
    val = int.from_bytes(digest[:8], "big") / (2**64)
    return val < probability
