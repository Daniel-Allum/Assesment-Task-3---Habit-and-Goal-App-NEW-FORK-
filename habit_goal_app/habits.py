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


def get_previous_period_start(frequency, period_start):
    """Return the previous tracking period start date."""
    if frequency == "daily":
        return period_start - timedelta(days=1)
    if frequency == "weekly":
        return period_start - timedelta(days=7)
    if frequency == "monthly":
        if period_start.month == 1:
            return period_start.replace(
                year=period_start.year - 1,
                month=12,
                day=1,
            )

        return period_start.replace(
            month=period_start.month - 1,
            day=1,
        )
    raise ValueError("Invalid frequency.")


def get_next_period_start(frequency, period_start):
    """Return the next tracking period start date."""
    if frequency == "daily":
        return period_start + timedelta(days=1)
    if frequency == "weekly":
        return period_start + timedelta(days=7)
    if frequency == "monthly":
        if period_start.month == 12:
            return period_start.replace(
                year=period_start.year + 1,
                month=1,
                day=1,
            )

        return period_start.replace(
            month=period_start.month + 1,
            day=1,
        )
    raise ValueError("Invalid frequency.")


def parse_date_value(value):
    """Convert a database date value into a Python date."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def get_or_create_current_entry(habit):
    """Retrieve or create the entry for the current habit period."""
    db = get_db()
    period_start, period_end = get_period_dates(habit["frequency"])
    entry = db.execute(
        (
            "SELECT id, habit_id, period_start, period_end, "
            "amount_completed, is_completed, updated_at "
            "FROM habit_entries "
            "WHERE habit_id = ? AND period_start = ? AND period_end = ?"
        ),
        (habit["id"], period_start.isoformat(), period_end.isoformat()),
    ).fetchone()
    if entry is None:
        db.execute(
            (
                "INSERT INTO habit_entries "
                "(habit_id, period_start, period_end, amount_completed, "
                "is_completed) "
                "VALUES (?, ?, ?, 0, 0)"
            ),
            (habit["id"], period_start.isoformat(), period_end.isoformat()),
        )
        db.commit()
        entry = db.execute(
            (
                "SELECT id, habit_id, period_start, period_end, "
                "amount_completed, is_completed, updated_at "
                "FROM habit_entries "
                "WHERE habit_id = ? AND period_start = ? AND period_end = ?"
            ),
            (
                habit["id"],
                period_start.isoformat(),
                period_end.isoformat(),
            ),
        ).fetchone()
    return entry


def recalculate_streaks(habit_id, frequency):
    """Recalculate current streak and longest streak from completed entries."""
    db = get_db()
    completed_entries = db.execute(
        (
            "SELECT period_start FROM habit_entries "
            "WHERE habit_id = ? AND is_completed = 1 "
            "ORDER BY period_start ASC"
        ),
        (habit_id,),
    ).fetchall()
    completed_starts = [
        parse_date_value(entry["period_start"]) for entry in completed_entries
    ]
    completed_set = set(completed_starts)
    longest_streak = 0
    running_streak = 0
    previous_start = None
    for current_start in completed_starts:
        if previous_start is None:
            running_streak = 1
        elif current_start == get_next_period_start(
            frequency,
            previous_start,
        ):
            running_streak += 1
        else:
            running_streak = 1
        longest_streak = max(longest_streak, running_streak)
        previous_start = current_start
    current_period_start = get_period_dates(frequency)[0]
    if current_period_start in completed_set:
        streak_pointer = current_period_start
    else:
        streak_pointer = get_previous_period_start(
            frequency,
            current_period_start,
        )
    current_streak = 0
    while streak_pointer in completed_set:
        current_streak += 1
        streak_pointer = get_previous_period_start(
            frequency,
            streak_pointer,
        )
    db.execute(
        ("UPDATE habits SET current_streak = ?, longest_streak = ? " "WHERE id = ?"),
        (current_streak, longest_streak, habit_id),
    )
    db.commit()


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


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    """Create a new habit."""
    categories = get_user_categories()
    if not categories:
        flash("Create at least one category before creating a habit.", "error")
        return redirect(url_for("categories.create"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category_id_raw = request.form.get("category_id", "").strip()
        frequency = request.form.get("frequency", "").strip()
        target_amount_raw = request.form.get("target_amount", "").strip()
        unit = request.form.get("unit", "").strip()
        error = None
        category_id = None
        target_amount = None

        if not name:
            error = "Habit name is required."
        elif len(name) > 80:
            error = "Habit name must contain no more than 80 characters."
        elif not category_id_raw:
            error = "Category is required."
        else:
            try:
                category_id = int(category_id_raw)
            except ValueError:
                error = "Invalid category selected."

        if error is None and not category_belongs_to_user(category_id):
            error = "Invalid category selected."
        if error is None and frequency not in ("daily", "weekly", "monthly"):
            error = "Frequency must be daily, weekly or monthly."
        if error is None:
            try:
                target_amount = float(target_amount_raw)
            except ValueError:
                error = "Target amount must be a number."
        if error is None and target_amount <= 0:
            error = "Target amount must be greater than 0."
        if error is None and not unit:
            error = "Unit is required."
        if error is None and len(unit) > 20:
            error = "Unit must contain no more than 20 characters."
        if error is None:
            db = get_db()

            cursor = db.execute(
                (
                    "INSERT INTO habits "
                    "(user_id, category_id, name, description, frequency, "
                    "target_amount, unit) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)"
                ),
                (
                    g.user["id"],
                    category_id,
                    name,
                    description,
                    frequency,
                    target_amount,
                    unit,
                ),
            )

            habit_id = cursor.lastrowid
            db.commit()
            flash("Habit created successfully.", "success")
            return redirect(url_for("habits.details", habit_id=habit_id))
        flash(error, "error")

    return render_template("habits/create.html", categories=categories)


@bp.route("/<int:habit_id>")
@login_required
def details(habit_id):
    """Display one habit and its current tracking period."""
    habit = get_habit(habit_id)
    current_entry = get_or_create_current_entry(habit)
    progress_percent = round(
        (current_entry["amount_completed"] / habit["target_amount"]) * 100,
        1,
    )

    recent_entries = (
        get_db()
        .execute(
            (
                "SELECT period_start, period_end, amount_completed, "
                "is_completed, updated_at "
                "FROM habit_entries "
                "WHERE habit_id = ? "
                "ORDER BY period_start DESC "
                "LIMIT 5"
            ),
            (habit_id,),
        )
        .fetchall()
    )

    return render_template(
        "habits/details.html",
        habit=habit,
        current_entry=current_entry,
        progress_percent=progress_percent,
        recent_entries=recent_entries,
    )


@bp.post("/<int:habit_id>/record")
@login_required
def record(habit_id):
    """Set the completed amount for the current habit period."""
    habit = get_habit(habit_id)

    if habit["is_active"] != 1:
        flash("Inactive habits cannot be updated.", "error")
        return redirect(url_for("habits.details", habit_id=habit_id))
    current_entry = get_or_create_current_entry(habit)
    amount_raw = request.form.get("amount_completed", "").strip()
    error = None

    try:
        amount_completed = float(amount_raw)
    except ValueError:
        error = "Amount completed must be a number."
    if error is None and amount_completed < 0:
        error = "Amount completed cannot be negative."
    if error is not None:
        flash(error, "error")
        return redirect(url_for("habits.details", habit_id=habit_id))
    is_completed = 1 if amount_completed >= habit["target_amount"] else 0
    db = get_db()

    db.execute(
        (
            "UPDATE habit_entries "
            "SET amount_completed = ?, is_completed = ?, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?"
        ),
        (amount_completed, is_completed, current_entry["id"]),
    )

    db.commit()
    recalculate_streaks(habit_id, habit["frequency"])
    if is_completed:
        flash("Habit target reached for this period.", "success")
    else:
        flash("Habit progress updated successfully.", "success")

    return redirect(url_for("habits.details", habit_id=habit_id))


@bp.route("/<int:habit_id>/update", methods=("GET", "POST"))
@login_required
def update(habit_id):
    """Update a habit's main details."""
    habit = get_habit(habit_id)
    categories = get_user_categories()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category_id_raw = request.form.get("category_id", "").strip()
        frequency = request.form.get("frequency", "").strip()
        target_amount_raw = request.form.get("target_amount", "").strip()
        unit = request.form.get("unit", "").strip()
        is_active = 1 if request.form.get("is_active") else 0
        error = None
        category_id = None
        target_amount = None

        if not name:
            error = "Habit name is required."
        elif len(name) > 80:
            error = "Habit name must contain no more than 80 characters."
        elif not category_id_raw:
            error = "Category is required."
        else:
            try:
                category_id = int(category_id_raw)
            except ValueError:
                error = "Invalid category selected."

        if error is None and not category_belongs_to_user(category_id):
            error = "Invalid category selected."
        if error is None and frequency not in ("daily", "weekly", "monthly"):
            error = "Frequency must be daily, weekly or monthly."
        if error is None:
            try:
                target_amount = float(target_amount_raw)
            except ValueError:
                error = "Target amount must be a number."
        if error is None and target_amount <= 0:
            error = "Target amount must be greater than 0."
        if error is None and not unit:
            error = "Unit is required."
        if error is None and len(unit) > 20:
            error = "Unit must contain no more than 20 characters."
        if error is None:
            db = get_db()

            db.execute(
                (
                    "UPDATE habits "
                    "SET category_id = ?, name = ?, description = ?, "
                    "frequency = ?, target_amount = ?, unit = ?, "
                    "is_active = ? "
                    "WHERE id = ? AND user_id = ?"
                ),
                (
                    category_id,
                    name,
                    description,
                    frequency,
                    target_amount,
                    unit,
                    is_active,
                    habit_id,
                    g.user["id"],
                ),
            )

            db.commit()
            recalculate_streaks(habit_id, frequency)
            flash("Habit updated successfully.", "success")
            return redirect(url_for("habits.details", habit_id=habit_id))
        flash(error, "error")

    return render_template(
        "habits/update.html",
        habit=habit,
        categories=categories,
    )


@bp.route("/<int:habit_id>/history")
@login_required
def history(habit_id):
    """Display all tracking records for a habit."""
    habit = get_habit(habit_id)
    entries = (
        get_db()
        .execute(
            (
                "SELECT period_start, period_end, amount_completed, "
                "is_completed, updated_at "
                "FROM habit_entries "
                "WHERE habit_id = ? "
                "ORDER BY period_start DESC"
            ),
            (habit_id,),
        )
        .fetchall()
    )

    return render_template(
        "habits/history.html",
        habit=habit,
        entries=entries,
    )


@bp.post("/<int:habit_id>/delete")
@login_required
def delete(habit_id):
    """Delete a habit owned by the current user."""
    get_habit(habit_id)
    db = get_db()
    db.execute(
        "DELETE FROM habits WHERE id = ? AND user_id = ?",
        (habit_id, g.user["id"]),
    )
    db.commit()
    flash("Habit deleted successfully.", "success")

    return redirect(url_for("habits.index"))
