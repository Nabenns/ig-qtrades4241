"""One-shot DB migration: add columns introduced after initial schema.

SQLAlchemy `create_all` only creates new tables — it doesn't alter existing ones.
This script applies idempotent ALTER TABLE statements for new columns.

Usage:
    uv run python scripts/migrate_db.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("data/ig_qt.db")


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def main() -> int:
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        # post_drafts.dynamic_hashtags (added with review flow)
        if table_exists(conn, "post_drafts") and not column_exists(
            conn, "post_drafts", "dynamic_hashtags"
        ):
            conn.execute("ALTER TABLE post_drafts ADD COLUMN dynamic_hashtags JSON DEFAULT '[]'")
            print("Added: post_drafts.dynamic_hashtags")

        # ig_account_state.warmup_active + warmup_started_at (added in M7)
        if table_exists(conn, "ig_account_state"):
            if not column_exists(conn, "ig_account_state", "warmup_active"):
                conn.execute(
                    "ALTER TABLE ig_account_state ADD COLUMN warmup_active BOOLEAN DEFAULT 0"
                )
                print("Added: ig_account_state.warmup_active")
            if not column_exists(conn, "ig_account_state", "warmup_started_at"):
                conn.execute(
                    "ALTER TABLE ig_account_state ADD COLUMN warmup_started_at DATETIME"
                )
                print("Added: ig_account_state.warmup_started_at")

        conn.commit()
        print("Migration complete.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
