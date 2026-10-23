import os
import sqlite3
from pathlib import Path

# Тест хийхдээ CAMPUS_DB_PATH-аар түр зуурын DB заана.
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "campus.db"


def get_database_path() -> Path:
    return Path(os.getenv("CAMPUS_DB_PATH", str(DEFAULT_DATABASE_PATH)))


# Хуучин кодтой нийцүүлэхийн тулд хэвээр үлдээв.
DATABASE_PATH = DEFAULT_DATABASE_PATH

# Хичээлд анхнаасаа өгөх өнгөнүүд (дараалан ашиглана).
# Өнгө ялгах чадвар сул хүмүүст ч ялгарахаар шалгасан дараалал.
COURSE_COLORS = [
    "#4f46e5",
    "#0891b2",
    "#ea580c",
    "#16a34a",
    "#db2777",
    "#9333ea",
    "#b45309",
    "#2563eb",
]


def get_connection():
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_table_columns(connection, table_name: str) -> set:
    return {
        row["name"]
        for row in connection.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }


def add_column_if_missing(connection, table_name: str, column: str, definition: str):
    """Хуучин DB-д багана байхгүй бол нэмнэ (өгөгдөл устгахгүй)."""
    if column not in get_table_columns(connection, table_name):
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column} {definition}"
        )


def pick_course_color(connection, user_id: int) -> str:
    count = connection.execute(
        "SELECT COUNT(*) FROM courses WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    return COURSE_COLORS[count % len(COURSE_COLORS)]


def get_or_create_course(connection, user_id: int, name: str) -> int:
    """Хичээлийн нэрээр хайж, байхгүй бол шинээр үүсгээд id-г буцаана."""
    row = connection.execute(
        """
        SELECT id FROM courses
        WHERE user_id = ? AND name = ? COLLATE NOCASE
        """,
        (user_id, name),
    ).fetchone()

    if row is not None:
        return row["id"]

    cursor = connection.execute(
        """
        INSERT INTO courses (user_id, name, color)
        VALUES (?, ?, ?)
        """,
        (user_id, name, pick_course_color(connection, user_id)),
    )
    return cursor.lastrowid


def migrate_existing_courses(connection):
    """course_id-гүй хуучин даалгавруудын хичээлийг courses хүснэгтэд шилжүүлнэ."""
    rows = connection.execute(
        """
        SELECT DISTINCT user_id, course
        FROM assignments
        WHERE course_id IS NULL AND user_id IS NOT NULL
        """
    ).fetchall()

    for row in rows:
        course_id = get_or_create_course(
            connection,
            row["user_id"],
            row["course"],
        )
        connection.execute(
            """
            UPDATE assignments
            SET course_id = ?
            WHERE user_id = ? AND course = ? AND course_id IS NULL
            """,
            (course_id, row["user_id"], row["course"]),
        )


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
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#4f46e5',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, name)
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

        # Хуучин өгөгдөлд шинэ баганууд байхгүй бол нэмнэ.
        add_column_if_missing(
            connection,
            "assignments",
            "user_id",
            "INTEGER REFERENCES users(id)",
        )
        add_column_if_missing(
            connection,
            "assignments",
            "priority",
            "TEXT NOT NULL DEFAULT 'medium'",
        )
        add_column_if_missing(
            connection,
            "assignments",
            "notes",
            "TEXT NOT NULL DEFAULT ''",
        )
        add_column_if_missing(
            connection,
            "assignments",
            "course_id",
            "INTEGER REFERENCES courses(id)",
        )
        add_column_if_missing(
            connection,
            "assignments",
            "completed_at",
            "TEXT",
        )

        # Сургуулийн самбараас татсан мэдэгдлүүд (бүх хэрэглэгчид нийтлэг).
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_id TEXT NOT NULL,
                ntt_id TEXT NOT NULL,
                title TEXT NOT NULL,
                writer TEXT NOT NULL DEFAULT '',
                posted_at TEXT NOT NULL,
                pinned INTEGER NOT NULL DEFAULT 0,
                url TEXT NOT NULL,
                fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (board_id, ntt_id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_notices_posted
            ON notices(posted_at)
            """
        )

        # Хэрэглэгч олширох үед хурдан хайхад зориулсан индексүүд.
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_assignments_user
            ON assignments(user_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_assignments_course
            ON assignments(course_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_courses_user
            ON courses(user_id)
            """
        )

        # Өмнө нь дууссан ч дуусгасан огноогүй даалгаврууд.
        connection.execute(
            """
            UPDATE assignments
            SET completed_at = created_at
            WHERE completed = 1 AND completed_at IS NULL
            """
        )

        migrate_existing_courses(connection)


if __name__ == "__main__":
    init_database()
    print(f"Database initialized: {get_database_path()}")
