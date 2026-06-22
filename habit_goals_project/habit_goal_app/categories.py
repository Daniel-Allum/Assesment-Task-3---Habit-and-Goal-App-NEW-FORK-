import sqlite3

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
    "categories",
    __name__,
    url_prefix="/categories",
)


def get_category(category_id):
    """Retrieve a category owned by the current user."""
    category = (
        get_db()
        .execute(
            "SELECT id, name, created_at FROM categories WHERE id = ? AND user_id = ?",
            (category_id, g.user["id"]),
        )
        .fetchone()
    )
    if category is None:
        abort(404)
    return category


@bp.route("/")
@login_required
def index():
    """Display all categories belonging to the user."""
    categories = (
        get_db()
        .execute(
            """SELECT categories.id, categories.name, categories.created_at,
            COUNT(DISTINCT goals.id) AS goal_count,
            COUNT(DISTINCT habits.id) AS habit_count
        FROM categories
        LEFT JOIN goals ON goals.category_id = categories.id
        LEFT JOIN habits ON habits.category_id = categories.id
        WHERE categories.user_id = ?
        GROUP BY categories.id, categories.name, categories.created_at
        ORDER BY categories.name COLLATE NOCASE
        """,
            (g.user["id"],),
        )
        .fetchall()
    )

    return render_template("categories/index.html", categories=categories)


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    """Create a new category."""

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        error = None

        if not name:
            error = "category name is required."
        elif len(name) > 40:
            error = "Category name must contain no more than 40 characters."

        if error is None:
            db = get_db()

            try:
                db.execute(
                    "INSERT INTO categories (user_id, name) VALUES (?, ?)",
                    (g.user["id"], name),
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = "You already have a category with that name."
            else:
                flash("Category created successfully.", "Success")
                return redirect(url_for("categories.index"))
        flash(error, "error")

    return render_template(
        "categories/form.html",
        page_title="Create Category",
        category=None,
    )


@bp.route("/<int:category_id>/update", methods=("GET", "POST"))
@login_required
def update(category_id):
    """Rename an existing category"""
    category = get_category(category_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        error = None

        if not name:
            error = "Category name is required."
        elif len(name) > 40:
            error = "Category name must contain no more than 40 characters."

        if error is None:
            db = get_db()

            try:
                db.execute(
                    "UPDATE categories SET name = ? WHERE id = ? AND user_id = ?",
                    (name, category_id, g.user["id"]),
                )
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                error = "You already have a category with that name."
            else:
                flash("Category updated successfully.", "success")
                return redirect(url_for("categories.index"))
        flash(error, "error")

    return render_template(
        "categories/form.html",
        page_title="Rename Category",
        category=category,
    )


@bp.post("/<int:category_id>/delete")
@login_required
def delete(category_id):
    """Delete an unused category."""

    get_category(category_id)
    db = get_db()

    try:
        db.execute(
            "DELETE FROM categories WHERE id = ? AND user_id = ?",
            (category_id, g.user["id"]),
        )
        db.commit()

    except sqlite3.IntegrityError:
        db.rollback()
        flash(
            "This category cannot be deleted because it is assigned to a goal or habit.",
            "error",
        )

    else:
        flash("Category deleted successfully.", "success")

    return redirect(url_for("categories.index"))
