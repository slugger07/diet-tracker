"""
CRUD operations for NutriLog India.

Every public function accepts an aiosqlite.Connection and uses parameterised
queries exclusively (no string concatenation).
"""

from __future__ import annotations

import datetime
from typing import Any

import aiosqlite


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize(name: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return " ".join(name.lower().strip().split())


def _today() -> str:
    return datetime.date.today().isoformat()


# ── Food Cache ────────────────────────────────────────────────────────────────

async def get_cached_nutrition(
    conn: aiosqlite.Connection,
    food_name: str,
    ttl_days: int = 30,
) -> dict[str, Any] | None:
    """Return cached nutrition for *food_name* if fresh, else None."""
    normalized = _normalize(food_name)
    cursor = await conn.execute(
        """
        SELECT *
          FROM food_cache
         WHERE food_name_normalized = ?
           AND julianday('now') - julianday(updated_at) <= ?
        """,
        (normalized, ttl_days),
    )
    row = await cursor.fetchone()
    if row is None:
        return None

    # Bump search_count
    await conn.execute(
        "UPDATE food_cache SET search_count = search_count + 1 WHERE id = ?",
        (row["id"],),
    )
    await conn.commit()
    return dict(row)


async def upsert_food_cache(
    conn: aiosqlite.Connection,
    *,
    food_name: str,
    calories_kcal: float | None = None,
    protein_g: float | None = None,
    carbs_g: float | None = None,
    fat_g: float | None = None,
    fiber_g: float | None = None,
    serving_size: str | None = None,
    serving_weight_g: float | None = None,
    source: str = "web_search",
    source_url: str | None = None,
    confidence: str = "medium",
) -> int:
    """Insert or update a food cache entry. Returns the row id."""
    normalized = _normalize(food_name)
    cursor = await conn.execute(
        """
        INSERT INTO food_cache
            (food_name, food_name_normalized, calories_kcal, protein_g, carbs_g,
             fat_g, fiber_g, serving_size, serving_weight_g, source, source_url,
             confidence, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(food_name_normalized) DO UPDATE SET
            calories_kcal    = excluded.calories_kcal,
            protein_g        = excluded.protein_g,
            carbs_g          = excluded.carbs_g,
            fat_g            = excluded.fat_g,
            fiber_g          = excluded.fiber_g,
            serving_size     = excluded.serving_size,
            serving_weight_g = excluded.serving_weight_g,
            source           = excluded.source,
            source_url       = excluded.source_url,
            confidence       = excluded.confidence,
            updated_at       = CURRENT_TIMESTAMP,
            search_count     = food_cache.search_count + 1
        """,
        (
            food_name,
            normalized,
            calories_kcal,
            protein_g,
            carbs_g,
            fat_g,
            fiber_g,
            serving_size,
            serving_weight_g,
            source,
            source_url,
            confidence,
        ),
    )
    await conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


# ── Food Logs ─────────────────────────────────────────────────────────────────

async def insert_food_log(
    conn: aiosqlite.Connection,
    *,
    user_name: str,
    meal_type: str,
    food_name: str,
    quantity: float,
    unit: str | None = None,
    calories_kcal: float | None = None,
    protein_g: float | None = None,
    carbs_g: float | None = None,
    fat_g: float | None = None,
    fiber_g: float | None = None,
    logged_at: str | None = None,
) -> int:
    """Insert a single food log entry. Returns the row id."""
    date = logged_at or _today()
    cursor = await conn.execute(
        """
        INSERT INTO food_logs
            (user_name, meal_type, food_name, quantity, unit,
             calories_kcal, protein_g, carbs_g, fat_g, fiber_g, logged_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_name,
            meal_type,
            food_name,
            quantity,
            unit,
            calories_kcal,
            protein_g,
            carbs_g,
            fat_g,
            fiber_g,
            date,
        ),
    )
    await conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def get_logs_for_date(
    conn: aiosqlite.Connection,
    user_name: str,
    date: str | None = None,
) -> list[dict[str, Any]]:
    """Return all food logs for a user on a given date."""
    date = date or _today()
    cursor = await conn.execute(
        """
        SELECT * FROM food_logs
         WHERE user_name = ? AND logged_at = ?
         ORDER BY created_at ASC
        """,
        (user_name, date),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_logs_range(
    conn: aiosqlite.Connection,
    user_name: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Return food logs for a user within a date range (inclusive)."""
    cursor = await conn.execute(
        """
        SELECT * FROM food_logs
         WHERE user_name = ? AND logged_at BETWEEN ? AND ?
         ORDER BY logged_at DESC, created_at ASC
        """,
        (user_name, start_date, end_date),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_food_log(conn: aiosqlite.Connection, log_id: int, user_name: str) -> bool:
    """Delete a food log entry. Returns True if a row was deleted."""
    cursor = await conn.execute(
        "DELETE FROM food_logs WHERE id = ? AND user_name = ?",
        (log_id, user_name),
    )
    await conn.commit()
    return cursor.rowcount > 0


# ── Daily Summary ─────────────────────────────────────────────────────────────

async def refresh_daily_summary(
    conn: aiosqlite.Connection,
    user_name: str,
    date: str | None = None,
) -> dict[str, Any] | None:
    """Recompute and upsert the daily summary for a given date."""
    date = date or _today()
    cursor = await conn.execute(
        """
        SELECT
            COALESCE(SUM(calories_kcal * quantity), 0) AS total_calories,
            COALESCE(SUM(protein_g     * quantity), 0) AS total_protein,
            COALESCE(SUM(carbs_g       * quantity), 0) AS total_carbs,
            COALESCE(SUM(fat_g         * quantity), 0) AS total_fat,
            COALESCE(SUM(fiber_g       * quantity), 0) AS total_fiber,
            COUNT(*)                                    AS meal_count
          FROM food_logs
         WHERE user_name = ? AND logged_at = ?
        """,
        (user_name, date),
    )
    row = await cursor.fetchone()
    if row is None or row["meal_count"] == 0:
        return None

    data = dict(row)
    await conn.execute(
        """
        INSERT INTO daily_summary
            (user_name, log_date, total_calories, total_protein, total_carbs,
             total_fat, total_fiber, meal_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_name, log_date) DO UPDATE SET
            total_calories = excluded.total_calories,
            total_protein  = excluded.total_protein,
            total_carbs    = excluded.total_carbs,
            total_fat      = excluded.total_fat,
            total_fiber    = excluded.total_fiber,
            meal_count     = excluded.meal_count
        """,
        (
            user_name,
            date,
            data["total_calories"],
            data["total_protein"],
            data["total_carbs"],
            data["total_fat"],
            data["total_fiber"],
            data["meal_count"],
        ),
    )
    await conn.commit()
    data["user_name"] = user_name
    data["log_date"] = date
    return data


async def get_daily_summary(
    conn: aiosqlite.Connection,
    user_name: str,
    date: str | None = None,
) -> dict[str, Any] | None:
    """Return the precomputed daily summary."""
    date = date or _today()
    cursor = await conn.execute(
        """
        SELECT * FROM daily_summary
         WHERE user_name = ? AND log_date = ?
        """,
        (user_name, date),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_summary_range(
    conn: aiosqlite.Connection,
    user_name: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """Return daily summaries within a date range."""
    cursor = await conn.execute(
        """
        SELECT * FROM daily_summary
         WHERE user_name = ? AND log_date BETWEEN ? AND ?
         ORDER BY log_date ASC
        """,
        (user_name, start_date, end_date),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ── User helpers ──────────────────────────────────────────────────────────────

async def get_all_users(conn: aiosqlite.Connection) -> list[str]:
    """Return a sorted list of distinct user names."""
    cursor = await conn.execute(
        "SELECT DISTINCT user_name FROM food_logs ORDER BY user_name"
    )
    rows = await cursor.fetchall()
    return [r["user_name"] for r in rows]


async def get_frequent_foods(
    conn: aiosqlite.Connection,
    user_name: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return most frequently logged foods for a user."""
    cursor = await conn.execute(
        """
        SELECT food_name, COUNT(*) AS log_count,
               ROUND(AVG(calories_kcal), 1) AS avg_calories
          FROM food_logs
         WHERE user_name = ?
         GROUP BY food_name
         ORDER BY log_count DESC
         LIMIT ?
        """,
        (user_name, limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]

