"""One-time: batch-generate ~10 evergreen drafts via LLM. Run manually."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import TypeAdapter

from ig_qt.analyst.evergreen import store_evergreen_drafts
from ig_qt.analyst.prompts.loader import load_prompt
from ig_qt.analyst.schemas import AngleDraft
from ig_qt.config import load_config
from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.llm.factory import build_llm_provider
from ig_qt.llm.router_9 import Router9Provider
from ig_qt.logging_setup import configure_logging


async def _main() -> int:
    cfg = load_config(Path("config.yaml"))
    configure_logging(log_dir=cfg.paths.data_dir / "logs", level="INFO", json_logs=False)
    engine = build_engine(cfg.paths.data_dir / "ig_qt.db")
    init_schema(engine)
    # Long-running batch (10 drafts ≈ 8k output tokens) needs a generous timeout.
    provider: Any
    if cfg.llm.provider == "router_9":
        provider = Router9Provider(
            base_url=cfg.llm.base_url,
            api_key=cfg.llm.api_key.get_secret_value(),
            timeout=300.0,
        )
    else:
        provider = build_llm_provider(cfg.llm)
    p = load_prompt("evergreen.v1")
    resp = await provider.complete_json(
        system=p.system,
        user=p.render_user(),
        model=cfg.llm.composer_model,
        temperature=0.7,
        max_output_tokens=8000,
    )
    if resp.parsed is None:
        try:
            resp_obj: Any = json.loads(resp.content)
        except json.JSONDecodeError:
            logger.error("evergreen_llm_invalid_json content={}", resp.content[:1000])
            return 1
    else:
        resp_obj = resp.parsed

    # LLM may return: {"drafts": [...]} | [...] | {"items"|"posts"|"data": [...]}
    items: Any = None
    if isinstance(resp_obj, list):
        items = resp_obj
    elif isinstance(resp_obj, dict):
        for key in ("drafts", "items", "posts", "data", "evergreen", "results"):
            if isinstance(resp_obj.get(key), list):
                items = resp_obj[key]
                break
        if items is None:
            # Fallback: take first list-typed value
            for v in resp_obj.values():
                if isinstance(v, list):
                    items = v
                    break

    if not items:
        logger.error(
            "evergreen_llm_no_drafts shape={} preview={}",
            type(resp_obj).__name__,
            json.dumps(resp_obj, ensure_ascii=False)[:1000],
        )
        return 1

    drafts = TypeAdapter(list[AngleDraft]).validate_python(items)
    with session_scope(engine) as s:
        store_evergreen_drafts(s, drafts)
    logger.info("evergreen_generated count={}", len(drafts))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
