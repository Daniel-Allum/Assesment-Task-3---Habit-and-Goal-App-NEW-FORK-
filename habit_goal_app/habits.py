from datetime import date, timedelta

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from .auth import login_required
from .db import get_db

bp = Blueprint(
    "habits",
    __name__,
    url_prefix="/habits",
)


def get_user_categories():
    """Retrieve all categories owned by the current user."""
    return (
        get_db()
        .execute(
            (
                "SELECT id, name FROM categories"
                "Where user_id = ?"
                "ORDER BY name COLLATE NOCASE"
            ),
            (g.user["id"],),
        )
        .fetchall()
    )


def category_belongs_to_user(category_id):
    """Check whether the selected category belongs to the current user."""
    category = (
        get_db()
        .execute(
            "SELECT id FROM categories WHERE id = ? AND user_id = ?",
            (category_id, g.user["id"]),
        )
        .fetchone()
    )
    return category is not None


def get_habit(habit_id):
    """Retrieve one habit owned by the current user."""
    habit = (
        get_db()
        .execute(
            (
                "SELECT habits.id, habits.user_id, habits.category_id, "
                "habits.name, habits.description, habits.frequency, "
                "habits.target_amount, habits.unit, habits.current_streak, "
                "habits.longest_streak, habits.is_active, habits.created_at, "
                "categories.name AS category_name "
                "FROM habits "
                "LEFT JOIN categories ON categories.id = habits.category_id "
                "WHERE habits.id = ? AND habits.user_id = ?"
            ),
            (habit_id, g.user["id"]),
        )
        .fetchone()
    )
    if habit is None:
        abort(404)
    return habit


def get_period_dates(frequency, selected_date=None):
    """Return the start and end dates for the current tracking period."""

    if selected_date is None:
        selected_date = date.today()

    if frequency == "daily":
        period_start = selected_date
        period_end = selected_date

    elif frequency == "weekly":
        period_start = selected_date - timedelta(days=selected_date.weekday())
        period_end = period_start + timedelta(days=6)

    elif frequency == "monthly":
        period_start = selected_date.replace(day=1)

        if selected_date.month == 12:
            next_month = selected_date.replace(
                year=selected_date.year + 1,
                month=1,
                day=1,
            )
        else:
            next_month = selected_date.replace(
                month=selected_date.month + 1,
                day=1,
            )
        period_end = next_month - timedelta(days=1)

    else:
        raise ValueError("Invalid frequency.")
    return period_start, period_end


@bp.route("/")
@login_required
def index():
    """Display habits belonging to the current user."""
    habits = (
        get_db()
        .execute(
            """
        SELECT habits.id, habits.name, habits.description, habits.frequency,
            habits.target_amount, habits.unit, habits.current_streak,
            habits.longest_streak, habits.is_active,
            categories.name AS category_name
        FROM habits
        LEFT JOIN categories ON categories.id = habits.category_id
        WHERE habits.user_id = ?
        ORDER BY habits.is_active DESC, habits.current_streak DESC, habits.created_at DESC
        """,
            (g.user["id"],),
        )
        .fetchall()
    )
    return render_template("habits/index.html", habits=habits)
