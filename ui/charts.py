"""
Visualisation helpers for NutriLog India.

Uses Streamlit's built-in charting (backed by Altair) — no extra deps needed.
"""

from __future__ import annotations

import datetime
from typing import Any

import streamlit as st


def show_weekly_chart(summaries: list[dict[str, Any]]) -> None:
    """
    Render a bar/line chart of daily calories + macros for the past week.
    """
    if not summaries:
        st.info("Not enough data for weekly trends yet. Keep logging!")
        return

    # Prepare data
    dates = []
    calories = []
    protein = []
    carbs = []
    fat = []

    for s in summaries:
        dates.append(s.get("log_date", ""))
        calories.append(s.get("total_calories", 0))
        protein.append(s.get("total_protein", 0))
        carbs.append(s.get("total_carbs", 0))
        fat.append(s.get("total_fat", 0))

    # Calorie trend
    st.markdown("#### \U0001F525 Calorie Trend")
    st.bar_chart(
        data={"Date": dates, "Calories": calories},
        x="Date",
        y="Calories",
        color="#FF6B6B",
    )

    # Macro breakdown
    st.markdown("#### \U0001F4AA Macro Trend")
    st.line_chart(
        data={
            "Date": dates,
            "Protein (g)": protein,
            "Carbs (g)": carbs,
            "Fat (g)": fat,
        },
        x="Date",
        y=["Protein (g)", "Carbs (g)", "Fat (g)"],
    )


def show_macro_donut(summary: dict[str, Any]) -> None:
    """
    Show today's macro split as a simple metric display.
    (Streamlit doesn't have native donut charts, so we use metrics.)
    """
    if not summary:
        return

    total_pro = summary.get("total_protein", 0)
    total_carb = summary.get("total_carbs", 0)
    total_fat = summary.get("total_fat", 0)
    total_fiber = summary.get("total_fiber", 0)

    # Macro calories
    pro_cal = total_pro * 4
    carb_cal = total_carb * 4
    fat_cal = total_fat * 9
    total_macro_cal = pro_cal + carb_cal + fat_cal

    st.markdown("#### \U0001F967 Macro Split")
    if total_macro_cal > 0:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Protein", f"{total_pro:.0f}g", f"{pro_cal / total_macro_cal * 100:.0f}%")
        with col2:
            st.metric("Carbs", f"{total_carb:.0f}g", f"{carb_cal / total_macro_cal * 100:.0f}%")
        with col3:
            st.metric("Fat", f"{total_fat:.0f}g", f"{fat_cal / total_macro_cal * 100:.0f}%")
        with col4:
            st.metric("Fiber", f"{total_fiber:.0f}g")
    else:
        st.caption("Log some food to see your macro split!")


def show_frequent_foods(foods: list[dict[str, Any]]) -> None:
    """Display a table of most frequently logged foods."""
    if not foods:
        st.caption("No frequently logged foods yet.")
        return

    st.markdown("#### \u2B50 Your Most Logged Foods")
    for i, f in enumerate(foods[:10], 1):
        name = f.get("food_name", "Unknown")
        count = f.get("log_count", 0)
        avg_cal = f.get("avg_calories", 0)
        st.markdown(
            f"**{i}.** {name} — logged **{count}x** "
            f"(avg {avg_cal:.0f} kcal)"
        )


def date_range_selector() -> tuple[str, str]:
    """Let the user pick a date range for history view."""
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("From", value=week_ago, max_value=today)
    with col2:
        end = st.date_input("To", value=today, max_value=today)

    if start > end:
        st.warning("Start date must be before end date.")
        start, end = end, start

    return start.isoformat(), end.isoformat()

