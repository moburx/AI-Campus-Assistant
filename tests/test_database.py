"""Хуучин DB-г шинэ бүтэц рүү шилжүүлэх (migration) тест."""

import sqlite3

from backend.database import get_database_path, init_database


def create_old_schema(path):
    """Өмнөх хувилбарын (priority, course_id, courses хүснэгтгүй) DB."""
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            country TEXT NOT NULL DEFAULT 'Other',
            preferred_language TEXT NOT NULL DEFAULT 'en',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            course TEXT NOT NULL,
            deadline TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES users(id)
        );
        INSERT INTO users (username, email, password_hash)
        VALUES ('old', 'old@example.com', 'x');
        INSERT INTO assignments (title, course, deadline, completed, user_id)
        VALUES ('A', 'Math', '2026-10-20', 0, 1),
               ('B', 'Math', '2026-10-21', 1, 1),
               ('C', 'Art', '2026-10-22', 0, 1);
        """
    )
    connection.commit()
    connection.close()


def test_migration_keeps_data_and_adds_courses():
    path = get_database_path()
    create_old_schema(path)

    init_database()
    init_database()  # Хоёр удаа ажиллуулахад алдаа гарахгүй байх ёстой.

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row

    rows = connection.execute(
        "SELECT title, course, course_id, priority, completed_at FROM assignments ORDER BY id"
    ).fetchall()
    courses = connection.execute(
        "SELECT id, name FROM courses ORDER BY name"
    ).fetchall()

    assert [row["title"] for row in rows] == ["A", "B", "C"]
    assert all(row["priority"] == "medium" for row in rows)
    assert all(row["course_id"] is not None for row in rows)
    assert rows[0]["course_id"] == rows[1]["course_id"]
    assert rows[1]["completed_at"] is not None
    assert rows[0]["completed_at"] is None
    assert [course["name"] for course in courses] == ["Art", "Math"]

    connection.close()
