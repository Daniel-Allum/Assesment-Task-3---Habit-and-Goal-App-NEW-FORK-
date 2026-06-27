from flask import (
    Blueprint,
    g,
    render_template,
)

from .auth import login_required
from .db import get_db

bp = Blueprint(
    "dashboard",
    __name__,
)


@bp.route("/")
@login_required
def index():
    """Display the main user dashboard."""
    db = get_db()
    user_id = g.user["id"]

    counts = {
        "active_goals": db.execute(
            "SELECT COUNT(*) AS total FROM goals WHERE user_id = ? AND status = 'active'",
            (user_id,),
        ).fetchone()["total"],
        "completed_goals": db.execute(
            "SELECT COUNT(*) AS total FROM goals WHERE user_id = ? AND status = 'completed'",
            (user_id,),
        ).fetchone()["total"],
        "active_habits": db.execute(
            "SELECT COUNT(*) AS total FROM habits WHERE user_id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()["total"],
        "categories": db.execute(
            "SELECT COUNT(*) AS total FROM categories WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"],
    }

    top_goals = db.execute(
        """
        SELECT goals.id, goals.name, goals.current_progress, goals.target_value, goals.unit, goals.deadline, goals.is_high_priority, categories.name AS category_name
        FROM goals
        LEFT JOIN categories ON categories.id = goals.category_id
        WHERE goals.user_id = ? AND goals.status = 'active'
        ORDER BY goals.is_high_priority DESC, CASE WHEN goals.deadline IS NULL THEN 1 ELSE 0 END, goals.deadline ASC, goals.created_at DESC
        LIMIT 3
        """,
        (user_id,),
    ).fetchall()

    top_habits = db.execute(
        """
        SELECT habits.id, habits.name, habits.frequency, habits.current_streak, habits.longest_streak, habits.target_amount, habits.unit, categories.name AS category_name
        FROM habits
        LEFT JOIN categories ON categories.id = habits.category_id
        WHERE habits.user_id = ? AND habits.is_active = 1
        ORDER BY habits.current_streak DESC, habits.longest_streak DESC, habits.created_at DESC
        LIMIT 3
        """,
        (user_id,),
    ).fetchall()

    return render_template(
        "dashboard/index.html",
        counts=counts,
        top_goals=top_goals,
        top_habits=top_habits,
    )
