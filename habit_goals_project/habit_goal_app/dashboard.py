from flask import (
    Blueprint,
    g,
    render_template,
)

from .auth import login_required
from .db import get_db

db = Blueprint(
    "dashboard",
    __name__,
)


@db.route("/")
@login_required
def index():
    """Display the main user dashboard."""
    db = get_db()
    user_id = g.user["id"]
