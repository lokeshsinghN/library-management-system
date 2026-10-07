import os
import sqlite3
from contextlib import contextmanager

from flask import current_app


@contextmanager
def get_db():
    """Open a database connection for one operation and always close it."""
    connection = sqlite3.connect(current_app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    """Create the library tables and the default admin account if needed."""
    from werkzeug.security import generate_password_hash

    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        category TEXT NOT NULL,
        isbn TEXT NOT NULL UNIQUE,
        publisher TEXT NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity >= 0),
        available_quantity INTEGER NOT NULL CHECK (
            available_quantity >= 0 AND available_quantity <= quantity
        )
    );

    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE RESTRICT,
        member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
        issue_date TEXT NOT NULL,
        due_date TEXT NOT NULL,
        return_date TEXT,
        overdue_days INTEGER NOT NULL DEFAULT 0 CHECK (overdue_days >= 0),
        fine REAL NOT NULL DEFAULT 0 CHECK (fine >= 0)
    );
    """
    with get_db() as connection:
        connection.executescript(schema)
        admin = connection.execute(
            "SELECT id FROM users WHERE username = ?", ("admin",)
        ).fetchone()
        if admin is None:
            connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("admin", generate_password_hash(os.environ.get("LIBRARY_ADMIN_PASSWORD", "admin123"))),
            )
