"""
Reusable Streamlit UI components for NutriLog India.
"""

from __future__ import annotations

import streamlit as st
from typing import Any


# ── Meal type emoji mapping ───────────────────────────────────────────────────

MEAL_EMOJIS = {
    "breakfast": "\U0001F305",  # sunrise
    "lunch": "\u2600\uFE0F",   # sun
    "dinner": "\U0001F319",    # crescent moon
    "snack": "\U0001F36A",     # cookie
}

MEAL_LABELS = {
    "breakfast": "Breakfast",
    "lunch": "Lunch",
    "dinner": "Dinner",
    "snack": "Snack",
}


# ── Food input form ──────────────────────────────────────────────────────────

def food_input_form() -> tuple[str, str] | None:
    """
    Render the food input form. Returns (user_input, meal_type) or None.
    """
    with st.form("food_form", clear_on_submit=True):
        user_input = st.text_area(
            "What did you eat?",
            placeholder="e.g. 2 roti, dal fry, and a glass of chaas",
            height=80,
            max_chars=500,
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            meal_type = st.radio(
                "Meal",
                options=["breakfast", "lunch", "dinner", "snack"],
                format_func=lambda x: f"{MEAL_EMOJIS.get(x, '')} {MEAL_LABELS.get(x, x)}",
                horizontal=True,
            )
        with col2:
            submitted = st.form_submit_button(
                "Log It \U0001F37D\uFE0F",
                use_container_width=True,
                type="primary",
            )

    if submitted and user_input and user_input.strip():
        return (user_input.strip(), meal_type)
    return None


# ── Nutrition results card ────────────────────────────────────────────────────

def show_logged_items(
    items: list[dict[str, Any]],
    meal_type: str,
) -> None:
    """Display the just-logged food items with nutrition."""
    emoji = MEAL_EMOJIS.get(meal_type, "\U0001F37D\uFE0F")
    st.success(f"{emoji} **{MEAL_LABELS.get(meal_type, meal_type)}** logged!")

    for item in items:
        qty = item.get("quantity", 1)
        name = item.get("food", "Unknown")
        cal = item.get("calories_kcal", 0) * qty
        pro = item.get("protein_g", 0) * qty
        unit = item.get("unit", "serving")
        serving = item.get("serving_size", "")

        st.markdown(
            f"&nbsp;&nbsp;&nbsp;&nbsp;"
            f"**{qty:.0f}x {name}** ({unit}) "
            f"— **{cal:.0f} kcal** | {pro:.1f}g protein"
            f"{'  (' + serving + ')' if serving else ''}"
        )


# ── Daily log view ────────────────────────────────────────────────────────────

def show_daily_log(logs: list[dict[str, Any]]) -> None:
    """Display all food logs for a day, grouped by meal type."""
    if not logs:
        st.info("No food logged yet today. Start by typing what you ate above!")
        return

    # Group by meal type
    grouped: dict[str, list[dict[str, Any]]] = {}
    for log in logs:
        mt = log.get("meal_type", "snack")
        grouped.setdefault(mt, []).append(log)

    meal_order = ["breakfast", "lunch", "dinner", "snack"]
    for mt in meal_order:
        if mt not in grouped:
            continue

        emoji = MEAL_EMOJIS.get(mt, "")
        st.markdown(f"#### {emoji} {MEAL_LABELS.get(mt, mt)}")

        for log in grouped[mt]:
            qty = log.get("quantity", 1)
            name = log.get("food_name", "Unknown")
            cal = (log.get("calories_kcal") or 0) * qty
            pro = (log.get("protein_g") or 0) * qty
            unit = log.get("unit", "")

            col1, col2, col3 = st.columns([4, 2, 1])
            with col1:
                st.markdown(f"**{qty:.0f}x {name}** ({unit})")
            with col2:
                st.markdown(f"**{cal:.0f}** kcal | **{pro:.1f}**g P")
            with col3:
                if st.button("\U0000274C", key=f"del_{log.get('id', 0)}", help="Remove"):
                    st.session_state[f"delete_{log['id']}"] = True
                    st.rerun()


# ── Summary progress bars ────────────────────────────────────────────────────

# Recommended daily values (general adult, can be made configurable)
DAILY_TARGETS = {
    "calories": 2000,
    "protein": 60,
    "carbs": 250,
    "fat": 65,
    "fiber": 30,
}

NUTRIENT_COLORS = {
    "calories": "#FF6B6B",
    "protein": "#4ECDC4",
    "carbs": "#45B7D1",
    "fat": "#F7DC6F",
    "fiber": "#82E0AA",
}


def show_daily_summary(summary: dict[str, Any] | None) -> None:
    """Render the daily nutrition summary with progress bars."""
    if not summary:
        return

    st.markdown("---")
    st.markdown("### \U0001F4CA Daily Summary")

    nutrients = [
        ("Calories", summary.get("total_calories", 0), DAILY_TARGETS["calories"], "kcal"),
        ("Protein", summary.get("total_protein", 0), DAILY_TARGETS["protein"], "g"),
        ("Carbs", summary.get("total_carbs", 0), DAILY_TARGETS["carbs"], "g"),
        ("Fat", summary.get("total_fat", 0), DAILY_TARGETS["fat"], "g"),
        ("Fiber", summary.get("total_fiber", 0), DAILY_TARGETS["fiber"], "g"),
    ]

    for name, current, target, unit_label in nutrients:
        pct = min(current / target, 1.0) if target > 0 else 0
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f"**{name}**")
        with col2:
            st.progress(pct, text=f"{current:.0f} / {target} {unit_label}")


def show_insight(insight: str) -> None:
    """Display the AI-generated daily insight."""
    if insight:
        st.markdown("---")
        st.info(f"\U0001F4A1 {insight}")


# ── User selector ─────────────────────────────────────────────────────────────

def user_selector(users: list[str], default_user: str) -> str:
    """Render a user selector in the sidebar."""
    all_users = list(dict.fromkeys([default_user] + users))  # deduplicate, keep order

    selected = st.sidebar.selectbox(
        "User",
        options=all_users,
        index=0,
    )

    new_user = st.sidebar.text_input(
        "Or add new user",
        placeholder="Name",
        max_chars=50,
    )
    if new_user and new_user.strip():
        return new_user.strip().lower()

    return selected or default_user

