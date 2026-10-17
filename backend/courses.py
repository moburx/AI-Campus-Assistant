"""Хичээл (course) удирдах API.

Хичээл бүр хэрэглэгчид харьяалагдана. Даалгавар нэмэхэд хичээлийн нэрээр
автоматаар үүсдэг ба энд нэр, өнгийг нь засаж, хэрэггүйг нь устгана.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from backend.auth import get_current_user
from backend.database import get_connection, pick_course_color

router = APIRouter(prefix="/api/courses", tags=["courses"])

COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    color: Optional[str] = Field(default=None, pattern=COLOR_PATTERN)


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    color: Optional[str] = Field(default=None, pattern=COLOR_PATTERN)


COURSE_SELECT = """
    SELECT
        c.id,
        c.name,
        c.color,
        c.created_at,
        COUNT(a.id) AS total,
        COALESCE(SUM(a.completed), 0) AS completed
    FROM courses AS c
    LEFT JOIN assignments AS a
        ON a.course_id = c.id AND a.user_id = c.user_id
"""


def course_to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "color": row["color"],
        "created_at": row["created_at"],
        "total": row["total"],
        "completed": row["completed"],
    }


def fetch_course(connection, course_id: int, user_id: int):
    row = connection.execute(
        COURSE_SELECT
        + """
        WHERE c.id = ? AND c.user_id = ?
        GROUP BY c.id
        """,
        (course_id, user_id),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found.",
        )

    return row


def ensure_unique_name(connection, user_id: int, name: str, exclude_id: int = 0):
    duplicate = connection.execute(
        """
        SELECT id FROM courses
        WHERE user_id = ? AND name = ? COLLATE NOCASE AND id != ?
        """,
        (user_id, name, exclude_id),
    ).fetchone()

    if duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail="A course with this name already exists.",
        )


@router.get("")
def list_courses(current_user: dict = Depends(get_current_user)):
    with get_connection() as connection:
        rows = connection.execute(
            COURSE_SELECT
            + """
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.name COLLATE NOCASE
            """,
            (current_user["id"],),
        ).fetchall()

    return [course_to_dict(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_course(
    course: CourseCreate,
    current_user: dict = Depends(get_current_user),
):
    name = course.name.strip()

    if not name:
        raise HTTPException(
            status_code=422,
            detail="Course name cannot be empty.",
        )

    with get_connection() as connection:
        ensure_unique_name(connection, current_user["id"], name)

        color = course.color or pick_course_color(
            connection,
            current_user["id"],
        )

        cursor = connection.execute(
            """
            INSERT INTO courses (user_id, name, color)
            VALUES (?, ?, ?)
            """,
            (current_user["id"], name, color.lower()),
        )

        row = fetch_course(connection, cursor.lastrowid, current_user["id"])

    return course_to_dict(row)


@router.patch("/{course_id}")
def update_course(
    course_id: int,
    update: CourseUpdate,
    current_user: dict = Depends(get_current_user),
):
    if update.name is None and update.color is None:
        raise HTTPException(
            status_code=422,
            detail="Nothing to update.",
        )

    with get_connection() as connection:
        fetch_course(connection, course_id, current_user["id"])

        if update.name is not None:
            name = update.name.strip()

            if not name:
                raise HTTPException(
                    status_code=422,
                    detail="Course name cannot be empty.",
                )

            ensure_unique_name(
                connection,
                current_user["id"],
                name,
                exclude_id=course_id,
            )

            connection.execute(
                "UPDATE courses SET name = ? WHERE id = ? AND user_id = ?",
                (name, course_id, current_user["id"]),
            )
            # Даалгаврууд дээрх хичээлийн нэрийг ч шинэчилнэ.
            connection.execute(
                """
                UPDATE assignments SET course = ?
                WHERE course_id = ? AND user_id = ?
                """,
                (name, course_id, current_user["id"]),
            )

        if update.color is not None:
            connection.execute(
                "UPDATE courses SET color = ? WHERE id = ? AND user_id = ?",
                (update.color.lower(), course_id, current_user["id"]),
            )

        row = fetch_course(connection, course_id, current_user["id"])

    return course_to_dict(row)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as connection:
        row = fetch_course(connection, course_id, current_user["id"])

        # Даалгавартай хичээлийг устгавал даалгавар "хичээлгүй" болох тул хориглоно.
        if row["total"] > 0:
            raise HTTPException(
                status_code=409,
                detail="This course still has assignments.",
            )

        connection.execute(
            "DELETE FROM courses WHERE id = ? AND user_id = ?",
            (course_id, current_user["id"]),
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
