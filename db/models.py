"""
Database schema initialisation and migration for NutriLog India.

Uses aiosqlite for async SQLite access.  The schema is created once on first
run and upgraded idempotently so the app always starts cleanly.
"""

from __future__ import annotations

import aiosqlite
from pathlib import Path

# ── Schema DDL ────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
-- Cached nutrition data (self-building database)
CREATE TABLE IF NOT EXISTS food_cache (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    food_name           TEXT    NOT NULL,
    food_name_normalized TEXT   NOT NULL,
    calories_kcal       REAL,
    protein_g           REAL,
    carbs_g             REAL,
    fat_g               REAL,
    fiber_g             REAL,
    serving_size        TEXT,
    serving_weight_g    REAL,
    source              TEXT    DEFAULT 'web_search',
    source_url          TEXT,
    confidence          TEXT    DEFAULT 'medium',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    search_count        INTEGER DEFAULT 1,
    UNIQUE(food_name_normalized)
);

-- User food logs
CREATE TABLE IF NOT EXISTS food_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name       TEXT    NOT NULL,
    meal_type       TEXT    NOT NULL,
    food_name       TEXT    NOT NULL,
    quantity        REAL    NOT NULL,
    unit            TEXT,
    calories_kcal   REAL,
    protein_g       REAL,
    carbs_g         REAL,
    fat_g           REAL,
    fiber_g         REAL,
    logged_at       DATE    DEFAULT (DATE('now')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily summary (materialised for fast dashboard reads)
CREATE TABLE IF NOT EXISTS daily_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name       TEXT    NOT NULL,
    log_date        DATE    NOT NULL,
    total_calories  REAL    DEFAULT 0,
    total_protein   REAL    DEFAULT 0,
    total_carbs     REAL    DEFAULT 0,
    total_fat       REAL    DEFAULT 0,
    total_fiber     REAL    DEFAULT 0,
    meal_count      INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_name, log_date)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_food_cache_normalized
    ON food_cache(food_name_normalized);
CREATE INDEX IF NOT EXISTS idx_food_logs_user_date
    ON food_logs(user_name, logged_at);
CREATE INDEX IF NOT EXISTS idx_daily_summary_user_date
    ON daily_summary(user_name, log_date);
"""


async def get_connection(db_path: Path) -> aiosqlite.Connection:
    """Open (or create) the SQLite database and return an async connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def init_db(db_path: Path) -> None:
    """Create tables and indexes if they don't exist yet."""
    conn = await get_connection(db_path)
    try:
        await conn.executescript(_SCHEMA_SQL)
        await conn.commit()
    finally:
        await conn.close()

