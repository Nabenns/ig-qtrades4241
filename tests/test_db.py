"""Tests for DB layer."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from ig_qt.db import build_engine, init_schema, session_scope
from ig_qt.models import IGAccountState, RawNews


def test_init_schema_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = build_engine(db_path)
    init_schema(engine)
    with session_scope(engine) as s:
        s.add(
            RawNews(
                source="test",
                external_id="1",
                title="hello",
                url="https://x",
                dedup_key="abc",
            )
        )
        s.flush()
        rows = s.execute(select(RawNews)).scalars().all()
        assert len(rows) == 1
        assert rows[0].title == "hello"


def test_session_scope_rolls_back_on_error(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = build_engine(db_path)
    init_schema(engine)
    try:
        with session_scope(engine) as s:
            s.add(IGAccountState(username="u"))
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    with session_scope(engine) as s:
        rows = s.execute(select(IGAccountState)).scalars().all()
        assert rows == []
