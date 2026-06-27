from datetime import datetime

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
    "goals",
    __name__,
    url_prefix="/goals",
)


def get_goal(goal_id):
    """Retrieve one goal owned by the current user."""

    goal = (
        get_db()
        .execute(
            """
        SELECT goals.id, goals.user_id, goals.category_id, goals.name, 
        goals.description, goals.is_high_priority, goals.deadline, goals.target_value, 
        goals.current_progress, goals.unit, goals.status, goals.created_at, goals.completed_at, 
        categories.name AS category_name, ROUND((goals.current_progress / goals.target_value) * 100, 1) AS progress_percent
        FROM goals
        LEFT JOIN categories ON categories.id = goals.category_id
        WHERE goals.id = ? AND goals.user_id = ? 
        """,
            (goal_id, g.user["id"]),
        )
        .fetchone()
    )
    if goal is None:
        abort(404)
    return goal


def get_user_categories():
    """Retrieve all categories owned by the current user."""
    return (
        get_db()
        .execute(
            "SELECT id, name FROM categories WHERE user_id = ? ORDER BY name COLLATE NOCASE",
            (g.user["id"],),
        )
        .fetchall()
    )


def category_belongs_to_user(category_id):
    """Check whether a category belongs to the current user."""

    category = (
        get_db()
        .execute(
            "SELECT id FROM categories WHERE id = ? AND user_id = ?",
            (category_id, g.user["id"]),
        )
        .fetchone()
    )

    return category is not None


@bp.route("/")
@login_required
def index():
    """Display goals belonging to the current user."""

    goals = (
        get_db()
        .execute(
            """
        SELECT goals.id, goals.name, goals.description, goals.is_high_priority,
            goals.deadline, goals.target_value, goals.current_progress,
            goals.unit, goals.status, categories.name AS category_name
        FROM goals
        LEFT JOIN categories ON categories.id = goals.category_id
        WHERE goals.user_id = ?
        ORDER BY goals.status ASC, goals.is_high_priority DESC,
                CASE WHEN goals.deadline IS NULL THEN 1 ELSE 0 END,
                goals.deadline ASC, goals.created_at DESC
        """,
            (g.user["id"],),
        )
        .fetchall()
    )

    return render_template("goals/index.html", goals=goals)
