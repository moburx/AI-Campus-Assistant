import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent.parent / "campus.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                country TEXT NOT NULL DEFAULT 'Other',
                preferred_language TEXT NOT NULL DEFAULT 'en',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                course TEXT NOT NULL,
                deadline TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Хуучин өгөгдөлд user_id багана байхгүй бол нэмнэ.
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(assignments)"
            ).fetchall()
        }

        if "user_id" not in columns:
            connection.execute(
                """
                ALTER TABLE assignments
                ADD COLUMN user_id INTEGER REFERENCES users(id)
                """
            )


if __name__ == "__main__":
    init_database()
    print(f"Database initialized: {DATABASE_PATH}")