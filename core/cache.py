"""
High-level cache operations and the daily-insight generator.

This module ties together parsing, nutrition lookup, and logging into
a single pipeline that the UI / API layer can call.
"""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite

from core.parser import parse_food_input, ParsedMeal, FoodItem
from core.nutrition import get_nutrition, NutritionInfo
from core.llm import llm_complete
from db.queries import insert_food_log, refresh_daily_summary, get_logs_for_date
from config import get_settings

logger = logging.getLogger(__name__)


# ── Insight prompt ────────────────────────────────────────────────────────────

_INSIGHT_SYSTEM = """You are a friendly Indian nutrition coach. Given the user's daily food log and nutrition totals, provide a brief, actionable insight in 2-3 sentences.

Rules:
- Be culturally relevant — suggest Indian foods (paneer, eggs, dal, sprouts for protein; fruits, salads for fiber, etc.)
- Be encouraging, not preachy
- Keep it casual and friendly
- If protein is low, suggest specific Indian high-protein foods
- If fiber is low, suggest fruits, salads, or whole grains
- If calories are very low, gently suggest eating more
- If calories are high, suggest lighter options for remaining meals
- Use Indian context (katori, roti, chai, etc.)
- Keep response under 100 words"""


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def log_food_pipeline(
    user_input: str,
    user_name: str,
    conn: aiosqlite.Connection,
    *,
    meal_type_hint: str | None = None,
) -> dict[str, Any]:
    """
    End-to-end pipeline: parse → lookup nutrition → log → summarise.

    Returns a dict with:
        parsed: ParsedMeal
        nutrition: list of (FoodItem, NutritionInfo) tuples
        summary: daily summary dict
    """
    settings = get_settings()

    # 1. Parse the input
    parsed: ParsedMeal = await parse_food_input(user_input, meal_type_hint=meal_type_hint)

    # 2. Look up nutrition for each item
    results: list[tuple[FoodItem, NutritionInfo]] = []
    errors: list[str] = []

    for item in parsed.items:
        try:
            info = await get_nutrition(
                item.food,
                conn,
                is_restaurant=parsed.is_restaurant,
                ttl_days=settings.cache_ttl_days,
            )
            results.append((item, info))
        except Exception as exc:
            logger.warning("Nutrition lookup failed for '%s': %s", item.food, exc)
            errors.append(f"Could not find nutrition for '{item.food}'")

    # 3. Log each item
    for item, info in results:
        await insert_food_log(
            conn,
            user_name=user_name,
            meal_type=parsed.meal_type,
            food_name=item.food,
            quantity=item.quantity,
            unit=item.unit,
            calories_kcal=info.calories_kcal,
            protein_g=info.protein_g,
            carbs_g=info.carbs_g,
            fat_g=info.fat_g,
            fiber_g=info.fiber_g,
        )

    # 4. Refresh daily summary
    summary = await refresh_daily_summary(conn, user_name)

    return {
        "parsed": parsed,
        "nutrition": results,
        "errors": errors,
        "summary": summary,
    }


async def generate_daily_insight(
    conn: aiosqlite.Connection,
    user_name: str,
    date: str | None = None,
) -> str:
    """Generate a friendly LLM-powered nutrition insight for the day."""
    logs = await get_logs_for_date(conn, user_name, date)
    if not logs:
        return "No food logged yet today. Start by logging your breakfast!"

    # Build context
    total_cal = sum((l.get("calories_kcal") or 0) * (l.get("quantity") or 1) for l in logs)
    total_pro = sum((l.get("protein_g") or 0) * (l.get("quantity") or 1) for l in logs)
    total_carb = sum((l.get("carbs_g") or 0) * (l.get("quantity") or 1) for l in logs)
    total_fat = sum((l.get("fat_g") or 0) * (l.get("quantity") or 1) for l in logs)
    total_fiber = sum((l.get("fiber_g") or 0) * (l.get("quantity") or 1) for l in logs)

    food_list = ", ".join(
        f"{l['quantity']}x {l['food_name']}" for l in logs
    )

    prompt = f"""Today's food log for the user:
Foods eaten: {food_list}

Daily totals:
- Calories: {total_cal:.0f} kcal (target: ~2000 kcal)
- Protein: {total_pro:.1f}g (target: ~60g)
- Carbs: {total_carb:.1f}g (target: ~250g)
- Fat: {total_fat:.1f}g (target: ~65g)
- Fiber: {total_fiber:.1f}g (target: ~30g)

Provide a brief, friendly insight."""

    try:
        insight = await llm_complete(prompt, system=_INSIGHT_SYSTEM, temperature=0.5)
        return insight
    except Exception as exc:
        logger.warning("Insight generation failed: %s", exc)
        # Fallback to a simple rule-based insight
        tips: list[str] = []
        if total_pro < 40:
            tips.append("Protein is a bit low — try adding paneer, eggs, or a handful of roasted chana.")
        if total_fiber < 15:
            tips.append("Add some fiber with fruits, salad, or a bowl of sprouts.")
        if total_cal > 2500:
            tips.append("Calorie intake is on the higher side — consider lighter options for your next meal.")
        if total_cal < 1000 and len(logs) >= 2:
            tips.append("You might want to eat a bit more — your calorie intake seems low for the day.")
        if not tips:
            tips.append("Good balance so far! Keep it up.")
        return " ".join(tips)

