import sqlite3
from datetime import date, datetime

import click
from flask import current_app, g

sqlite3.register_convertor(
    "timestamp",
    lambda value: datetime.fromisoformat(
        value.decode("utf-8"),
    ),
)

sqlite3.register_converter(
    "date",
    lambda value: date.fromisoformat(value.decode("utf-8")),
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=(sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES),
        )
    g.db.row_factory = sqlite3.Row
    g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()

    with current_app.open_resource("schema.sql") as file:
        db.executescript(file.read().decode("utf-8"))
    db.commit()


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Initialized the habits and goals database.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
