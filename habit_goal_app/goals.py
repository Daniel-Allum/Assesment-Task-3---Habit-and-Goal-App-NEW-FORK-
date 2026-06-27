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


@bp.route("/completed")
@login_required
def completed():
    """Display completed goals belonging to the current user."""
    goals = (
        get_db()
        .execute(
            """
        SELECT goals.id, goals.name, goals.description, goals.is_high_priority, goals.deadline, 
        goals.target_value, goals.current_progress, goals.unit, goals.status, goals.completed_at, 
        categories.name AS category_name, ROUND((goals.current_progress / goals.target_value) * 100, 1) AS progress_percent
        FROM goals
        LEFT JOIN categories ON categories.id = goals.category_id
        WHERE goals.user_id = ? AND goals.status = 'completed'
        ORDER BY goals.completed_at DESC, goals.created_at DESC
        """,
            (g.user["id"],),
        )
        .fetchall()
    )
    return render_template("goals/completed.html", goals=goals)


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    """Create a new goal."""
    categories = get_user_categories()

    if not categories:
        flash("Create at least one category before creating a goal.", "error")
        return redirect(url_for("categories.create"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category_id_raw = request.form.get("category_id", "").strip()
        deadline = request.form.get("deadline", "").strip()
        target_value_raw = request.form.get("target_value", "").strip()
        current_progress_raw = request.form.get("current_progress", "").strip()
        unit = request.form.get("unit", "").strip()
        is_high_priority = 1 if request.form.get("is_high_priority") else 0

        error = None
        category_id = None
        target_value = None
        current_progress = None

        if not name:
            error = "Goal name is required."
        elif len(name) > 80:
            error = "Goal name must contain no more than 80 characters."
        elif not category_id_raw:
            error = "Category is required."
        else:
            try:
                category_id = int(category_id_raw)
            except ValueError:
                error = "Invalid category selected."

        if error is None and not category_belongs_to_user(category_id):
            error = "Invalid category selected."

        if error is None:
            try:
                target_value = float(target_value_raw)
            except ValueError:
                error = "Target value must be a number."

        if error is None and target_value <= 0:
            error = "Target value must be greater than 0."

        if error is None:
            try:
                current_progress = float(current_progress_raw)
            except ValueError:
                error = "Current progress must be a number."

        if error is None and current_progress < 0:
            error = "Current progress cannot be negative."

        if error is None and not unit:
            error = "Unit is required."

        if error is None and len(unit) > 20:
            error = "Unit must contain no more than 20 characters."

        if error is None and deadline:
            try:
                datetime.strptime(deadline, "%Y-%m-%d")
            except ValueError:
                error = "Deadline must be a valid date."

        if error is None:
            status = "completed" if current_progress >= target_value else "active"
            completed_at = (
                datetime.now().replace(microsecond=0) if status == "completed" else None
            )
            db = get_db()

            cursor = db.execute(
                "INSERT INTO goals (user_id, category_id, name, description, is_high_priority, deadline, target_value, current_progress, unit, status, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    g.user["id"],
                    category_id,
                    name,
                    description,
                    is_high_priority,
                    deadline if deadline else None,
                    target_value,
                    current_progress,
                    unit,
                    status,
                    completed_at,
                ),
            )
            goal_id = cursor.lastrowid

            if current_progress > 0:
                db.execute(
                    "INSERT INTO goal_progress_history (goal_id, previous_value, new_value) VALUES (?, ?, ?)",
                    (goal_id, 0, current_progress),
                )
            db.commit()
            flash("Goal created successfully.", "success")
            return redirect(url_for("goals.details", goal_id=goal_id))
        flash(error, "error")

    return render_template("goals/create.html", categories=categories)


@bp.route("/<int:goal_id>")
@login_required
def details(goal_id):
    """Display one individual goal."""
    goal = get_goal(goal_id)
    progress_history = (
        get_db()
        .execute(
            "SELECT previous_value, new_value, recorded_at FROM goal_progress_history WHERE goal_id = ? ORDER BY recorded_at DESC",
            (goal_id,),
        )
        .fetchall()
    )

    return render_template(
        "goals/details.html", goal=goal, progress_history=progress_history
    )


@bp.route("/<int:goal_id>/update", methods=("GET", "POST"))
@login_required
def update(goal_id):
    """Update goal details, excluding progress."""
    goal = get_goal(goal_id)
    categories = get_user_categories()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category_id_raw = request.form.get("category_id", "").strip()
        deadline = request.form.get("deadline", "").strip()
        target_value_raw = request.form.get("target_value", "").strip()
        unit = request.form.get("unit", "").strip()
        is_high_priority = 1 if request.form.get("is_high_priority") else 0

        error = None
        category_id = None
        target_value = None

        if not name:
            error = "Goal name is required."
        elif len(name) > 80:
            error = "Goal name must contain no more than 80 characters."
        elif not category_id_raw:
            error = "Category is required."
        else:
            try:
                category_id = int(category_id_raw)
            except ValueError:
                error = "Invalid category selected."

        if error is None and not category_belongs_to_user(category_id):
            error = "Invalid category selected."

        if error is None:
            try:
                target_value = float(target_value_raw)
            except ValueError:
                error = "Target value must be a number."

        if error is None and target_value <= 0:
            error = "Target value must be greater than 0."

        if error is None and not unit:
            error = "Unit is required."

        if error is None and len(unit) > 20:
            error = "Unit must contain no more than 20 characters."

        if error is None and deadline:
            try:
                datetime.strptime(deadline, "%Y-%m-%d")
            except ValueError:
                error = "Deadline must be a valid date."

        if error is None:
            current_progress = goal["current_progress"]
            should_complete = (
                current_progress >= target_value or goal["status"] == "completed"
            )
            status = "completed" if should_complete else "active"
            completed_at = goal["completed_at"]

            if should_complete and completed_at is None:
                completed_at = datetime.now().replace(microsecond=0)
            db = get_db()
            db.execute(
                """
                UPDATE goals SET category_id = ?, name = ?, description = ?, is_high_priority = ?, deadline = ?, target_value = ?, unit = ?, status = ?, completed_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    category_id,
                    name,
                    description,
                    is_high_priority,
                    deadline if deadline else None,
                    target_value,
                    unit,
                    status,
                    completed_at,
                    goal_id,
                    g.user["id"],
                ),
            )

            db.commit()
            flash("Goal updated successfully.", "success")
            return redirect(url_for("goals.details", goal_id=goal_id))
        flash(error, "error")

    return render_template("goals/update.html", goal=goal, categories=categories)
