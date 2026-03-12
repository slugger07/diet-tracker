"""
Nutrition extraction pipeline.

Flow: food item → cache check → web search → LLM extraction → cache store → return.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

import aiosqlite

from core.llm import llm_json
from core.search import search_nutrition, format_search_results
from db.queries import get_cached_nutrition, upsert_food_cache

logger = logging.getLogger(__name__)


# ── Pydantic model ────────────────────────────────────────────────────────────

class NutritionInfo(BaseModel):
    """Structured nutrition data for one serving of a food item."""
    food_name: str
    serving_size: str = "1 serving"
    serving_weight_g: float | None = None
    calories_kcal: float = Field(ge=0, le=5000)
    protein_g: float = Field(ge=0, le=500)
    carbs_g: float = Field(ge=0, le=500)
    fat_g: float = Field(ge=0, le=500)
    fiber_g: float = Field(ge=0, le=200)
    confidence: str = "medium"
    source: str = "web_search"
    source_url: str | None = None

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"high", "medium", "low"}:
            return "medium"
        return v


# ── LLM extraction prompt ────────────────────────────────────────────────────

_EXTRACT_SYSTEM = """You are a nutrition data extractor. Given web search results about a food item, extract the most accurate nutrition values PER SINGLE SERVING.

Rules:
- Prefer Indian sources (HealthifyMe, nutritionix.in, IFCT data, Indian food blogs)
- If values conflict across sources, prefer the median/most common value
- If the food is Indian, use typical Indian preparation methods and portion sizes
- For home-cooked food, use standard Indian home-cooking amounts of oil/ghee
- For restaurant/dhaba food, increase calories by ~30-50% due to extra oil/butter/cream
- All values should be for ONE standard serving (1 roti, 1 katori dal, 1 glass chai, etc.)
- Be accurate — these values will be used for daily nutrition tracking

Return ONLY valid JSON:
{
  "food_name": "descriptive name",
  "serving_size": "e.g. 1 medium piece (~35g)",
  "serving_weight_g": number_or_null,
  "calories_kcal": number,
  "protein_g": number,
  "carbs_g": number,
  "fat_g": number,
  "fiber_g": number,
  "confidence": "high|medium|low"
}"""


# ── Public API ────────────────────────────────────────────────────────────────

async def get_nutrition(
    food_name: str,
    conn: aiosqlite.Connection,
    *,
    is_restaurant: bool = False,
    ttl_days: int = 30,
) -> NutritionInfo:
    """
    Get nutrition info for a food item.

    1. Check SQLite cache
    2. If miss → web search → LLM extract → cache → return
    """
    # Adjust lookup key for restaurant variant
    cache_key = f"{food_name} (restaurant)" if is_restaurant else food_name

    # ── Step 1: Cache check ───────────────────────────────────────────────
    cached = await get_cached_nutrition(conn, cache_key, ttl_days=ttl_days)
    if cached:
        logger.info("Cache HIT for '%s'", cache_key)
        return NutritionInfo(
            food_name=cached["food_name"],
            serving_size=cached.get("serving_size") or "1 serving",
            serving_weight_g=cached.get("serving_weight_g"),
            calories_kcal=cached.get("calories_kcal") or 0,
            protein_g=cached.get("protein_g") or 0,
            carbs_g=cached.get("carbs_g") or 0,
            fat_g=cached.get("fat_g") or 0,
            fiber_g=cached.get("fiber_g") or 0,
            confidence=cached.get("confidence") or "medium",
            source=cached.get("source") or "cache",
            source_url=cached.get("source_url"),
        )

    # ── Step 2: Web search ────────────────────────────────────────────────
    logger.info("Cache MISS for '%s' — searching web", cache_key)
    search_results = await search_nutrition(food_name, max_results=5)
    search_text = format_search_results(search_results)

    # ── Step 3: LLM extraction ────────────────────────────────────────────
    context = f"Food item: {food_name}"
    if is_restaurant:
        context += "\n(This is restaurant/dhaba/outside food — adjust values upward for extra oil/butter)"
    context += f"\n\nWeb search results:\n{search_text}"

    raw = await llm_json(context, system=_EXTRACT_SYSTEM)

    # Capture source URL from first search result if available
    source_url = search_results[0]["href"] if search_results else None
    raw.setdefault("source_url", source_url)
    raw.setdefault("source", "web_search")

    try:
        info = NutritionInfo(**raw)
    except Exception as exc:
        logger.error(
            "Failed to validate nutrition for '%s': %s | raw=%s",
            food_name, exc, raw,
        )
        raise ValueError(
            f"Could not extract nutrition for '{food_name}'. "
            "The web search may not have returned useful results."
        ) from exc

    # ── Step 4: Cache the result ──────────────────────────────────────────
    await upsert_food_cache(
        conn,
        food_name=cache_key,
        calories_kcal=info.calories_kcal,
        protein_g=info.protein_g,
        carbs_g=info.carbs_g,
        fat_g=info.fat_g,
        fiber_g=info.fiber_g,
        serving_size=info.serving_size,
        serving_weight_g=info.serving_weight_g,
        source=info.source,
        source_url=info.source_url,
        confidence=info.confidence,
    )

    logger.info(
        "Nutrition for '%s': %s kcal (confidence: %s)",
        food_name, info.calories_kcal, info.confidence,
    )
    return info

