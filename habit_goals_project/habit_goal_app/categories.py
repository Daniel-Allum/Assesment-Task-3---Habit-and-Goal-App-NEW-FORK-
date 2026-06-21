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
