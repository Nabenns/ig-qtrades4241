"""Pre-publish activity simulation: timeline read + randomized sleep."""
from __future__ import annotations

import asyncio
import random
from typing import Protocol


class _SupportsWarmup(Protocol):
    def warmup(self) -> None: ...


async def simulate_pre_publish_activity(
    client: _SupportsWarmup,
    *,
    sleep_min: float = 8.0,
    sleep_max: float = 15.0,
    seed: int | None = None,
) -> None:
    rng = random.Random(seed) if seed is not None else random  # noqa: S311
    reads = rng.randint(1, 2)  # noqa: S311
    for _ in range(reads):
        client.warmup()
        if sleep_max > 0:
            await asyncio.sleep(rng.uniform(0.5, 2.0))  # noqa: S311
        else:
            await asyncio.sleep(0)
    if sleep_max > 0:
        await asyncio.sleep(rng.uniform(sleep_min, sleep_max))  # noqa: S311
    else:
        await asyncio.sleep(0)
