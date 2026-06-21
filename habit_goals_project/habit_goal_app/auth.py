import functools
import sqlite3

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=("GET", "POST"))
def register():
    """Register a new user account"""

    if g.user is not None:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get(
            "username",
            "",
        ).strip()
        password = request.form.get(
            "password",
            "",
        )
        error = None

        if len(username) < 3:
            error = "Username must contain at least 3 characters."
        elif len(username) > 30:
            error = "Username must contain no more than 30 characters."
        elif len(password) < 8:
            error = "Password must contain at least 8 characters."

        if error is None:
            db = get_db()
            try:
                db.execute(
                    """
                    INSERT INTO users (
                        username,
                        password_hash
                    )
                    VALUES (?, ?)
                    """,
                    (
                        username,
                        generate_password_hash(password),
                    ),
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = "That username is already registered."
            else:
                flash("Account created successfully. You can now log in", "success")

            return redirect(url_for("auth.login"))

        flash(error, "error")

    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    """Authenticate a user and create a session."""
    if g.user is not None:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get(
            "username",
            "",
        ).strip()
        password = request.form.get(
            "password",
            "",
        )
        db = get_db()

        user = db.execute(
            """
            SELECT
                id,
                username,
                password_hash
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        if user is None or not check_password_hash(
            user["password_hash"],
            password,
        ):
            flash(
                "Incorrect username or password.",
                "error",
            )

        else:
            session.clear()
            session["user_id"] = user["id"]

            return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html")


@bp.before_app_request
def load_logged_in_user():
    """Load the current user before every request."""
    user_id = session.get("user_id")

    if user_id is None:
        g.user = None
    else:
        g.user = (
            get_db()
            .execute(
                """
            SELECT
                id,
                username,
                created_at
            FROM users
            WHERE id = ?
            """,
                (user_id,),
            )
            .fetchone()
        )


@bp.post("/logout")
def logout():
    """Remove the current login session."""

    session.clear()

    return redirect(url_for("auth.login"))


def login_required(view):
    """Prevent signed-out users from accessing a route."""

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash(
                "Please log in to access that page.",
                "error",
            )

            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view
