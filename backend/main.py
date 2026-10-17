import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend import assistant, courses, stats
from backend.auth import (
    LanguageCode,
    create_access_token,
    get_current_user,
    get_user_by_id,
    password_hash,
)
from backend.database import get_connection, get_or_create_course, init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="AI Campus Assistant API",
    description="A campus assignment management API",
    version="2.0.0",
    lifespan=lifespan,
)

# Development-д зориулсан CORS тохиргоо.
# Frontend-ээ FastAPI-гаар үйлчлэхэд дараа нь үүнийг хязгаарлана.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "null",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(courses.router)
app.include_router(stats.router)
app.include_router(assistant.router)

Priority = Literal["high", "medium", "low"]


# ---------- Загварууд ----------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    country: str = Field(default="Other", min_length=1, max_length=50)
    preferred_language: LanguageCode = "en"


class UserLogin(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    country: Optional[str] = Field(default=None, min_length=1, max_length=50)
    preferred_language: Optional[LanguageCode] = None


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    course: str = Field(min_length=1, max_length=200)
    deadline: date
    priority: Priority = "medium"
    notes: str = Field(default="", max_length=1000)


class AssignmentUpdate(BaseModel):
    """Бүх талбар сонголттой: зөвхөн илгээсэн талбарыг шинэчилнэ."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    course: Optional[str] = Field(default=None, min_length=1, max_length=200)
    deadline: Optional[date] = None
    priority: Optional[Priority] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    completed: Optional[bool] = None


ASSIGNMENT_SELECT = """
    SELECT
        a.id,
        a.title,
        a.course,
        a.course_id,
        a.deadline,
        a.priority,
        a.notes,
        a.completed,
        a.completed_at,
        a.created_at,
        c.color AS course_color
    FROM assignments AS a
    LEFT JOIN courses AS c ON c.id = a.course_id
"""


def assignment_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "course": row["course"],
        "course_id": row["course_id"],
        "course_color": row["course_color"],
        "deadline": row["deadline"],
        "priority": row["priority"],
        "notes": row["notes"],
        "completed": bool(row["completed"]),
        "completed_at": row["completed_at"],
        "created_at": row["created_at"],
    }


def utc_now_text() -> str:
    """SQLite-ийн CURRENT_TIMESTAMP-тай ижил хэлбэр (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def clean_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} cannot be empty.",
        )
    return cleaned


def fetch_assignment(connection, assignment_id: int, user_id: int):
    row = connection.execute(
        ASSIGNMENT_SELECT + " WHERE a.id = ? AND a.user_id = ?",
        (assignment_id, user_id),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Assignment not found.",
        )

    return row


# ---------- Ерөнхий ----------
@app.get("/")
def root():
    return {
        "message": "Welcome to AI Campus Assistant API",
        "docs": "/docs",
    }


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# ---------- Хэрэглэгч ----------
@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate):
    username = user.username.strip()
    email = user.email.strip().lower()
    country = user.country.strip()
    preferred_language = user.preferred_language

    if not username or not email or not country:
        raise HTTPException(
            status_code=422,
            detail="Username, email, and country cannot be empty.",
        )

    hashed_password = password_hash.hash(user.password)

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (
                    username,
                    email,
                    password_hash,
                    country,
                    preferred_language
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    username,
                    email,
                    hashed_password,
                    country,
                    preferred_language,
                ),
            )

            user_id = cursor.lastrowid

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Username or email already exists.",
        )

    return {
        "id": user_id,
        "username": username,
        "email": email,
        "country": country,
        "preferred_language": preferred_language,
        "message": "Registration successful.",
    }


@app.post("/api/auth/login")
def login_user(user: UserLogin):
    username = user.username.strip()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, username, email, password_hash,
                   country, preferred_language
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

    if row is None or not password_hash.verify(
        user.password,
        row["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    access_token = create_access_token(row["id"])

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "country": row["country"],
            "preferred_language": row["preferred_language"],
        },
        "message": "Login successful.",
    }


@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.patch("/api/auth/me")
def update_me(
    update: UserUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Хэрэглэгч өөрийн хэл, улсаа солино."""
    changes = {}

    if update.preferred_language is not None:
        changes["preferred_language"] = update.preferred_language

    if update.country is not None:
        changes["country"] = clean_text(update.country, "Country")

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="Nothing to update.",
        )

    set_sql = ", ".join(f"{column} = ?" for column in changes)

    with get_connection() as connection:
        connection.execute(
            f"UPDATE users SET {set_sql} WHERE id = ?",
            (*changes.values(), current_user["id"]),
        )

    return get_user_by_id(current_user["id"])


# ---------- Даалгавар ----------
@app.get("/api/assignments")
def get_assignments(
    course_id: Optional[int] = Query(default=None),
    status_filter: Literal["all", "completed", "incomplete"] = Query(
        default="all",
        alias="status",
    ),
    current_user: dict = Depends(get_current_user),
):
    conditions = ["a.user_id = ?"]
    params = [current_user["id"]]

    if course_id is not None:
        conditions.append("a.course_id = ?")
        params.append(course_id)

    if status_filter == "completed":
        conditions.append("a.completed = 1")
    elif status_filter == "incomplete":
        conditions.append("a.completed = 0")

    with get_connection() as connection:
        rows = connection.execute(
            ASSIGNMENT_SELECT
            + " WHERE "
            + " AND ".join(conditions)
            + " ORDER BY a.id DESC",
            params,
        ).fetchall()

    return [assignment_to_dict(row) for row in rows]


@app.post(
    "/api/assignments",
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    assignment: AssignmentCreate,
    current_user: dict = Depends(get_current_user),
):
    title = clean_text(assignment.title, "Title")
    course = clean_text(assignment.course, "Course")

    with get_connection() as connection:
        course_id = get_or_create_course(
            connection,
            current_user["id"],
            course,
        )
        # Хичээлийн нэрийг courses хүснэгтэд байгаагаар нь (том/жижиг үсэг) хадгална.
        course = connection.execute(
            "SELECT name FROM courses WHERE id = ?",
            (course_id,),
        ).fetchone()["name"]

        cursor = connection.execute(
            """
            INSERT INTO assignments (
                title, course, course_id, deadline, priority, notes, user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                course,
                course_id,
                assignment.deadline.isoformat(),
                assignment.priority,
                assignment.notes.strip(),
                current_user["id"],
            ),
        )

        row = fetch_assignment(connection, cursor.lastrowid, current_user["id"])

    return assignment_to_dict(row)


@app.patch("/api/assignments/{assignment_id}")
def update_assignment(
    assignment_id: int,
    update: AssignmentUpdate,
    current_user: dict = Depends(get_current_user),
):
    changes = {}

    if update.title is not None:
        changes["title"] = clean_text(update.title, "Title")

    if update.deadline is not None:
        changes["deadline"] = update.deadline.isoformat()

    if update.priority is not None:
        changes["priority"] = update.priority

    if update.notes is not None:
        changes["notes"] = update.notes.strip()

    if update.completed is not None:
        changes["completed"] = int(update.completed)
        changes["completed_at"] = utc_now_text() if update.completed else None

    if not changes and update.course is None:
        raise HTTPException(
            status_code=422,
            detail="Nothing to update.",
        )

    with get_connection() as connection:
        current = fetch_assignment(connection, assignment_id, current_user["id"])

        # Аль хэдийн дууссан даалгаврыг дахин "дууссан" болгоход огноог бүү өөрчил.
        if update.completed and current["completed"]:
            changes["completed_at"] = current["completed_at"]

        if update.course is not None:
            course_name = clean_text(update.course, "Course")
            course_id = get_or_create_course(
                connection,
                current_user["id"],
                course_name,
            )
            changes["course_id"] = course_id
            changes["course"] = connection.execute(
                "SELECT name FROM courses WHERE id = ?",
                (course_id,),
            ).fetchone()["name"]

        set_sql = ", ".join(f"{column} = ?" for column in changes)
        connection.execute(
            f"UPDATE assignments SET {set_sql} WHERE id = ? AND user_id = ?",
            (*changes.values(), assignment_id, current_user["id"]),
        )

        row = fetch_assignment(connection, assignment_id, current_user["id"])

    return assignment_to_dict(row)


@app.delete(
    "/api/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_assignment(
    assignment_id: int,
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM assignments
            WHERE id = ? AND user_id = ?
            """,
            (assignment_id, current_user["id"]),
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Assignment not found.",
            )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
