"""
NutriLog India — Main Streamlit Application.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import sys
from pathlib import Path

import streamlit as st

# Ensure project root is on sys.path so imports work
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import get_settings
from db.models import init_db, get_connection
from db.queries import (
    get_logs_for_date,
    get_logs_range,
    delete_food_log,
    get_all_users,
    get_frequent_foods,
    get_summary_range,
    refresh_daily_summary,
)
from core.cache import log_food_pipeline, generate_daily_insight
from ui.components import (
    food_input_form,
    show_logged_items,
    show_daily_log,
    show_daily_summary,
    show_insight,
    user_selector,
    MEAL_EMOJIS,
    MEAL_LABELS,
)
from ui.charts import (
    show_weekly_chart,
    show_macro_donut,
    show_frequent_foods,
    date_range_selector,
)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Async helper ──────────────────────────────────────────────────────────────

# Dedicated event loop running in a background thread for all async work.
# This avoids conflicts with Streamlit's own event loop.
import concurrent.futures

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)
_LOOP: asyncio.AbstractEventLoop | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    global _LOOP
    if _LOOP is None or _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
    return _LOOP


def run_async(coro):
    """Run an async coroutine from synchronous Streamlit context."""
    loop = _get_loop()
    future = _EXECUTOR.submit(loop.run_until_complete, coro)
    return future.result(timeout=120)


# ── DB initialisation (cached) ────────────────────────────────────────────────

@st.cache_resource
def _init_database():
    """Initialise the database once per Streamlit session."""
    settings = get_settings()
    run_async(init_db(settings.db_path))
    return True


def _get_conn():
    settings = get_settings()
    return run_async(get_connection(settings.db_path))


# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NutriLog India",
    page_icon="\U0001F35B",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialise DB
_init_database()


# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    .stProgress > div > div > div > div {
        border-radius: 10px;
    }
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 10px 15px;
    }
    div[data-testid="stMetric"] label {
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("\U0001F35B NutriLog India")
st.sidebar.caption("AI-powered Indian food nutrition tracker")
st.sidebar.markdown("---")

# User selection
settings = get_settings()
conn_for_users = _get_conn()
try:
    existing_users = run_async(get_all_users(conn_for_users))
finally:
    run_async(conn_for_users.close())

current_user = user_selector(existing_users, settings.default_user)
st.sidebar.markdown(f"**Logged in as:** `{current_user}`")

# Navigation
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    options=["Today", "History", "Insights"],
    format_func=lambda x: {
        "Today": "\U0001F4C5 Today",
        "History": "\U0001F4C8 History",
        "Insights": "\U0001F4A1 Insights",
    }.get(x, x),
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "<small>Built with \U0001F1EE\U0001F1F3 love, \u20B90 budget</small>",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE: TODAY
# ══════════════════════════════════════════════════════════════════════════════

if page == "Today":
    st.title(f"\U0001F35B NutriLog India")
    today_str = datetime.date.today().strftime("%A, %d %B %Y")
    st.caption(f"Today: {today_str}")

    # ── Food input form ───────────────────────────────────────────────────
    result = food_input_form()

    if result:
        user_input, meal_type = result

        with st.spinner("Parsing your food and looking up nutrition..."):
            conn = _get_conn()
            try:
                pipeline_result = run_async(
                    log_food_pipeline(
                        user_input,
                        current_user,
                        conn,
                        meal_type_hint=meal_type,
                    )
                )

                # Show what was logged
                items_data = []
                for food_item, nutrition in pipeline_result["nutrition"]:
                    items_data.append({
                        "food": food_item.food,
                        "quantity": food_item.quantity,
                        "unit": food_item.unit,
                        "calories_kcal": nutrition.calories_kcal,
                        "protein_g": nutrition.protein_g,
                        "carbs_g": nutrition.carbs_g,
                        "fat_g": nutrition.fat_g,
                        "fiber_g": nutrition.fiber_g,
                        "serving_size": nutrition.serving_size,
                    })

                show_logged_items(items_data, meal_type)

                # Show errors if any
                if pipeline_result["errors"]:
                    for err in pipeline_result["errors"]:
                        st.warning(err)

            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                logger.exception("Pipeline error")
                st.error("Something went wrong. Please try again with a different description.")
            finally:
                run_async(conn.close())

    # ── Today's log ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(f"### \U0001F4CB Today's Log")

    conn = _get_conn()
    try:
        today_logs = run_async(get_logs_for_date(conn, current_user))

        # Handle deletions
        for log in today_logs:
            if st.session_state.get(f"delete_{log['id']}"):
                run_async(delete_food_log(conn, log["id"], current_user))
                run_async(refresh_daily_summary(conn, current_user))
                del st.session_state[f"delete_{log['id']}"]
                st.rerun()

        show_daily_log(today_logs)

        # ── Daily summary ─────────────────────────────────────────────────
        summary = run_async(refresh_daily_summary(conn, current_user))
        show_daily_summary(summary)

        # ── Macro split ───────────────────────────────────────────────────
        show_macro_donut(summary)

        # ── AI Insight ────────────────────────────────────────────────────
        if today_logs:
            if st.button("\U0001F4A1 Get AI Insight"):
                with st.spinner("Generating insight..."):
                    insight = run_async(generate_daily_insight(conn, current_user))
                    show_insight(insight)

    finally:
        run_async(conn.close())


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE: HISTORY
# ══════════════════════════════════════════════════════════════════════════════

elif page == "History":
    st.title("\U0001F4C8 History & Trends")

    start_date, end_date = date_range_selector()

    conn = _get_conn()
    try:
        # Weekly chart
        summaries = run_async(get_summary_range(conn, current_user, start_date, end_date))
        show_weekly_chart(summaries)

        # Detailed logs
        st.markdown("---")
        st.markdown("### \U0001F4CB Detailed Logs")

        logs = run_async(get_logs_range(conn, current_user, start_date, end_date))
        if logs:
            # Group by date
            by_date: dict[str, list] = {}
            for log in logs:
                d = log.get("logged_at", "Unknown")
                by_date.setdefault(d, []).append(log)

            for date_key in sorted(by_date.keys(), reverse=True):
                with st.expander(f"\U0001F4C5 {date_key} ({len(by_date[date_key])} items)"):
                    for log in by_date[date_key]:
                        qty = log.get("quantity", 1)
                        name = log.get("food_name", "Unknown")
                        cal = (log.get("calories_kcal") or 0) * qty
                        mt = log.get("meal_type", "snack")
                        emoji = MEAL_EMOJIS.get(mt, "")
                        st.markdown(
                            f"{emoji} **{qty:.0f}x {name}** — {cal:.0f} kcal "
                            f"({MEAL_LABELS.get(mt, mt)})"
                        )
        else:
            st.info("No logs found for this date range.")

    finally:
        run_async(conn.close())


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE: INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Insights":
    st.title("\U0001F4A1 Insights & Stats")

    conn = _get_conn()
    try:
        # Frequent foods
        foods = run_async(get_frequent_foods(conn, current_user, limit=10))
        show_frequent_foods(foods)

        # Weekly averages
        st.markdown("---")
        st.markdown("### \U0001F4CA Weekly Averages")

        today = datetime.date.today()
        week_ago = (today - datetime.timedelta(days=7)).isoformat()
        summaries = run_async(
            get_summary_range(conn, current_user, week_ago, today.isoformat())
        )

        if summaries:
            n = len(summaries)
            avg_cal = sum(s.get("total_calories", 0) for s in summaries) / n
            avg_pro = sum(s.get("total_protein", 0) for s in summaries) / n
            avg_carb = sum(s.get("total_carbs", 0) for s in summaries) / n
            avg_fat = sum(s.get("total_fat", 0) for s in summaries) / n
            avg_fiber = sum(s.get("total_fiber", 0) for s in summaries) / n

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Avg Calories", f"{avg_cal:.0f} kcal")
            with col2:
                st.metric("Avg Protein", f"{avg_pro:.1f}g")
            with col3:
                st.metric("Avg Carbs", f"{avg_carb:.1f}g")
            with col4:
                st.metric("Avg Fat", f"{avg_fat:.1f}g")
            with col5:
                st.metric("Avg Fiber", f"{avg_fiber:.1f}g")

            st.caption(f"Based on {n} day(s) of data")
        else:
            st.info("Not enough data for weekly averages. Keep logging!")

        # AI weekly insight
        st.markdown("---")
        if st.button("\U0001F9E0 Generate Weekly Insight"):
            with st.spinner("Analyzing your week..."):
                insight = run_async(generate_daily_insight(conn, current_user))
                show_insight(insight)

    finally:
        run_async(conn.close())

