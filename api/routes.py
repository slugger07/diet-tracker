"""
FastAPI REST API for NutriLog India.

Provides endpoints for food logging, nutrition lookup, and daily summaries.
The Streamlit UI can call these, or they can be used standalone.
"""

from __future__ import annotations

import datetime
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from config import get_settings
from db.models import init_db, get_connection
from core.cache import log_food_pipeline, generate_daily_insight
from core.nutrition import get_nutrition, NutritionInfo
from db.queries import (
    get_logs_for_date,
    get_logs_range,
    delete_food_log,
    get_daily_summary,
    get_summary_range,
    get_all_users,
    get_frequent_foods,
    refresh_daily_summary,
)

logger = logging.getLogger(__name__)

# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB on startup."""
    settings = get_settings()
    await init_db(settings.db_path)
    logger.info("Database initialised at %s", settings.db_path)
    yield


app = FastAPI(
    title="NutriLog India",
    description="AI-powered Indian food nutrition tracker",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request / Response models ─────────────────────────────────────────────────

class LogFoodRequest(BaseModel):
    """Request body for the food logging endpoint."""
    user_input: str = Field(..., min_length=1, max_length=500, description="Natural language food description")
    user_name: str = Field(default="default", min_length=1, max_length=50)
    meal_type: str | None = Field(default=None, description="breakfast, lunch, dinner, snack")

    @field_validator("user_input")
    @classmethod
    def sanitize_input(cls, v: str) -> str:
        return v.strip()

    @field_validator("meal_type")
    @classmethod
    def validate_meal_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if v not in {"breakfast", "lunch", "dinner", "snack"}:
            raise ValueError("meal_type must be breakfast, lunch, dinner, or snack")
        return v


class NutritionItem(BaseModel):
    food: str
    quantity: float
    unit: str
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    serving_size: str


class LogFoodResponse(BaseModel):
    meal_type: str
    items: list[NutritionItem]
    errors: list[str]
    summary: dict[str, Any] | None


class DailySummaryResponse(BaseModel):
    user_name: str
    log_date: str
    total_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    total_fiber: float
    meal_count: int


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_conn():
    settings = get_settings()
    return await get_connection(settings.db_path)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/log", response_model=LogFoodResponse)
async def log_food(req: LogFoodRequest):
    """
    Log food in natural language. The LLM parses, looks up nutrition, and saves.
    """
    conn = await _get_conn()
    try:
        result = await log_food_pipeline(
            req.user_input,
            req.user_name,
            conn,
            meal_type_hint=req.meal_type,
        )

        items = []
        for food_item, nutrition in result["nutrition"]:
            items.append(NutritionItem(
                food=food_item.food,
                quantity=food_item.quantity,
                unit=food_item.unit,
                calories_kcal=nutrition.calories_kcal,
                protein_g=nutrition.protein_g,
                carbs_g=nutrition.carbs_g,
                fat_g=nutrition.fat_g,
                fiber_g=nutrition.fiber_g,
                serving_size=nutrition.serving_size,
            ))

        return LogFoodResponse(
            meal_type=result["parsed"].meal_type,
            items=items,
            errors=result["errors"],
            summary=result["summary"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in /api/log")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing your food log. Please try again.",
        )
    finally:
        await conn.close()


@app.get("/api/logs")
async def get_logs(
    user_name: str = Query(default="default", min_length=1, max_length=50),
    date: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    """Get food logs for a user on a given date."""
    conn = await _get_conn()
    try:
        logs = await get_logs_for_date(conn, user_name, date)
        return {"logs": logs, "count": len(logs)}
    finally:
        await conn.close()


@app.get("/api/logs/range")
async def get_logs_by_range(
    user_name: str = Query(default="default"),
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
):
    """Get food logs for a date range."""
    conn = await _get_conn()
    try:
        logs = await get_logs_range(conn, user_name, start_date, end_date)
        return {"logs": logs, "count": len(logs)}
    finally:
        await conn.close()


@app.delete("/api/logs/{log_id}")
async def remove_food_log(
    log_id: int,
    user_name: str = Query(default="default"),
):
    """Delete a food log entry (only if owned by the user)."""
    conn = await _get_conn()
    try:
        deleted = await delete_food_log(conn, log_id, user_name)
        if not deleted:
            raise HTTPException(status_code=404, detail="Log entry not found or not owned by you.")
        # Refresh summary after deletion
        await refresh_daily_summary(conn, user_name)
        return {"deleted": True}
    finally:
        await conn.close()


@app.get("/api/summary", response_model=DailySummaryResponse | None)
async def daily_summary(
    user_name: str = Query(default="default"),
    date: str | None = Query(default=None),
):
    """Get the daily nutrition summary."""
    conn = await _get_conn()
    try:
        # Always refresh first to get latest
        summary = await refresh_daily_summary(conn, user_name, date)
        if not summary:
            return None
        return DailySummaryResponse(
            user_name=summary["user_name"],
            log_date=summary["log_date"],
            total_calories=summary["total_calories"],
            total_protein=summary["total_protein"],
            total_carbs=summary["total_carbs"],
            total_fat=summary["total_fat"],
            total_fiber=summary["total_fiber"],
            meal_count=summary["meal_count"],
        )
    finally:
        await conn.close()


@app.get("/api/summary/range")
async def summary_range(
    user_name: str = Query(default="default"),
    start_date: str = Query(...),
    end_date: str = Query(...),
):
    """Get daily summaries for a date range (for charts)."""
    conn = await _get_conn()
    try:
        summaries = await get_summary_range(conn, user_name, start_date, end_date)
        return {"summaries": summaries}
    finally:
        await conn.close()


@app.get("/api/insight")
async def daily_insight(
    user_name: str = Query(default="default"),
    date: str | None = Query(default=None),
):
    """Get an AI-generated daily nutrition insight."""
    conn = await _get_conn()
    try:
        insight = await generate_daily_insight(conn, user_name, date)
        return {"insight": insight}
    except Exception as exc:
        logger.exception("Insight generation failed")
        return {"insight": "Keep tracking your meals — consistency is key!"}
    finally:
        await conn.close()


@app.get("/api/users")
async def list_users():
    """List all users who have logged food."""
    conn = await _get_conn()
    try:
        users = await get_all_users(conn)
        return {"users": users}
    finally:
        await conn.close()


@app.get("/api/frequent-foods")
async def frequent_foods(
    user_name: str = Query(default="default"),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get the most frequently logged foods for a user."""
    conn = await _get_conn()
    try:
        foods = await get_frequent_foods(conn, user_name, limit=limit)
        return {"foods": foods}
    finally:
        await conn.close()


@app.get("/api/health")
async def health_check():
    """Simple health check."""
    return {"status": "healthy", "service": "nutrilog-india"}

