"""Даалгаврын API ба дахин ашиглах боломжтой функцууд.

Endpoint-ууд болон AI агент (backend/agent.py) хоёулаа энэ файлын
list/create/update/delete функцуудыг ашигладаг. Ингэснээр шалгалт,
хэрэглэгчийн тусгаарлалт нэг л газар бичигдэнэ.
"""

from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from backend.auth import get_current_user
from backend.database import get_connection, get_or_create_course

router = APIRouter(prefix="/api/assignments", tags=["assignments"])

Priority = Literal["high", "medium", "low"]
StatusFilter = Literal["all", "completed", "incomplete"]


# ---------- Загварууд ----------
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


def resolve_course(connection, user_id: int, course_name: str):
    """Хичээлийг олох/үүсгэх ба courses хүснэгтэд байгаа нэрийг буцаана."""
    course_id = get_or_create_course(
        connection,
        user_id,
        clean_text(course_name, "Course"),
    )
    name = connection.execute(
        "SELECT name FROM courses WHERE id = ?",
        (course_id,),
    ).fetchone()["name"]
    return course_id, name


# ---------- Дахин ашиглах функцууд ----------
def list_assignments(
    user_id: int,
    course_id: Optional[int] = None,
    status_filter: str = "all",
) -> list:
    conditions = ["a.user_id = ?"]
    params = [user_id]

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


def create_assignment(user_id: int, assignment: AssignmentCreate) -> dict:
    title = clean_text(assignment.title, "Title")

    with get_connection() as connection:
        course_id, course = resolve_course(connection, user_id, assignment.course)

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
                user_id,
            ),
        )

        row = fetch_assignment(connection, cursor.lastrowid, user_id)

    return assignment_to_dict(row)


def update_assignment(user_id: int, assignment_id: int, update: AssignmentUpdate) -> dict:
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
        current = fetch_assignment(connection, assignment_id, user_id)

        # Аль хэдийн дууссан даалгаврыг дахин "дууссан" болгоход огноог бүү өөрчил.
        if update.completed and current["completed"]:
            changes["completed_at"] = current["completed_at"]

        if update.course is not None:
            changes["course_id"], changes["course"] = resolve_course(
                connection,
                user_id,
                update.course,
            )

        set_sql = ", ".join(f"{column} = ?" for column in changes)
        connection.execute(
            f"UPDATE assignments SET {set_sql} WHERE id = ? AND user_id = ?",
            (*changes.values(), assignment_id, user_id),
        )

        row = fetch_assignment(connection, assignment_id, user_id)

    return assignment_to_dict(row)


def delete_assignment(user_id: int, assignment_id: int) -> None:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM assignments
            WHERE id = ? AND user_id = ?
            """,
            (assignment_id, user_id),
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Assignment not found.",
            )


# ---------- Endpoint-ууд ----------
@router.get("")
def get_assignments_endpoint(
    course_id: Optional[int] = Query(default=None),
    status_filter: StatusFilter = Query(default="all", alias="status"),
    current_user: dict = Depends(get_current_user),
):
    return list_assignments(current_user["id"], course_id, status_filter)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_assignment_endpoint(
    assignment: AssignmentCreate,
    current_user: dict = Depends(get_current_user),
):
    return create_assignment(current_user["id"], assignment)


@router.patch("/{assignment_id}")
def update_assignment_endpoint(
    assignment_id: int,
    update: AssignmentUpdate,
    current_user: dict = Depends(get_current_user),
):
    return update_assignment(current_user["id"], assignment_id, update)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment_endpoint(
    assignment_id: int,
    current_user: dict = Depends(get_current_user),
):
    delete_assignment(current_user["id"], assignment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
