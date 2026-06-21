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
