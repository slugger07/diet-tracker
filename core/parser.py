"""
Food input parser — converts natural language to structured food items.

Uses the LLM to understand Indian food context, portions, and meal types.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

from core.llm import llm_json

logger = logging.getLogger(__name__)


# ── Pydantic models for validated output ──────────────────────────────────────

class FoodItem(BaseModel):
    """A single parsed food item."""
    food: str = Field(..., min_length=1, description="Food name in English")
    quantity: float = Field(default=1.0, ge=0.1, le=100)
    unit: str = Field(default="serving", description="piece, katori, glass, plate, g, ml, etc.")

    @field_validator("food")
    @classmethod
    def clean_food_name(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, v: str) -> str:
        return v.strip().lower()


class ParsedMeal(BaseModel):
    """Result of parsing a user's food input."""
    meal_type: str = Field(default="snack", description="breakfast, lunch, dinner, snack")
    items: list[FoodItem] = Field(default_factory=list, min_length=1)
    is_restaurant: bool = Field(default=False, description="Whether food is from a restaurant/dhaba")

    @field_validator("meal_type")
    @classmethod
    def validate_meal_type(cls, v: str) -> str:
        v = v.strip().lower()
        valid = {"breakfast", "lunch", "dinner", "snack"}
        if v not in valid:
            return "snack"
        return v


# ── System prompt ─────────────────────────────────────────────────────────────

_PARSE_SYSTEM = """You are a nutrition assistant for Indian users. Parse the user's food input and extract individual food items with quantities.

Rules:
- Default to Indian food interpretations (roti = wheat chapati, not tortilla)
- Use Indian portion sizes (katori, glass, plate, piece)
- If quantity is missing, assume 1 standard serving
- If a food could mean multiple things, pick the most common Indian version
- Detect meal type from context clues (time of day words, food combinations)
  - Breakfast: poha, upma, paratha, idli, dosa, chai, bread-butter, cornflakes, oats
  - Lunch: rice, roti, dal, sabzi, curd, rajma, chole
  - Dinner: roti, sabzi, dal, khichdi
  - Snack: samosa, pakora, chai, biscuit, fruit, bhel, vada pav
- If the user mentions "restaurant", "dhaba", "outside", "takeout", "zomato", "swiggy", set is_restaurant to true
- Return ONLY valid JSON, no explanation

Output format:
{
  "meal_type": "breakfast|lunch|dinner|snack",
  "items": [
    {"food": "descriptive name", "quantity": number, "unit": "piece|katori|glass|plate|bowl|cup|tbsp|g|ml|serving"}
  ],
  "is_restaurant": false
}"""


# ── Public API ────────────────────────────────────────────────────────────────

async def parse_food_input(
    user_input: str,
    meal_type_hint: str | None = None,
) -> ParsedMeal:
    """
    Parse a natural-language food description into structured items.

    Parameters
    ----------
    user_input : str
        Free-text like "2 roti dal chaas"
    meal_type_hint : str, optional
        If the user already selected a meal type in the UI, pass it here
        so the LLM doesn't have to guess.
    """
    if not user_input or not user_input.strip():
        raise ValueError("Food input cannot be empty.")

    prompt = f'User food input: "{user_input.strip()}"'
    if meal_type_hint:
        prompt += f"\n(The user indicated this is: {meal_type_hint})"

    raw: dict[str, Any] = await llm_json(prompt, system=_PARSE_SYSTEM)

    # Override meal_type if user explicitly chose one
    if meal_type_hint:
        raw["meal_type"] = meal_type_hint

    try:
        parsed = ParsedMeal(**raw)
    except Exception as exc:
        logger.error("Failed to validate parsed meal: %s | raw=%s", exc, raw)
        raise ValueError(
            "Could not understand the food input. "
            "Please try rephrasing, e.g. '2 roti with dal and rice'."
        ) from exc

    logger.info(
        "Parsed '%s' → %d items (%s)",
        user_input,
        len(parsed.items),
        parsed.meal_type,
    )
    return parsed

