from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.database import get_connection, init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="AI Campus Assistant API",
    description="A campus assignment management API",
    version="1.0.0",
    lifespan=lifespan,
)

# Development-д зориулсан CORS тохиргоо.
# Frontend-ээ FastAPI-гаар үйлчлэхэд дараа нь үүнийг хязгаарлана.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "null",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    course: str = Field(min_length=1, max_length=200)
    deadline: str = Field(min_length=10, max_length=10)


class AssignmentUpdate(BaseModel):
    completed: bool


def assignment_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "course": row["course"],
        "deadline": row["deadline"],
        "completed": bool(row["completed"]),
        "created_at": row["created_at"],
    }


@app.get("/")
def root():
    return {
        "message": "Welcome to AI Campus Assistant API",
        "docs": "/docs",
    }


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/assignments")
def get_assignments():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, course, deadline, completed, created_at
            FROM assignments
            ORDER BY id DESC
            """
        ).fetchall()

    return [assignment_to_dict(row) for row in rows]


@app.post(
    "/api/assignments",
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(assignment: AssignmentCreate):
    title = assignment.title.strip()
    course = assignment.course.strip()

    if not title or not course:
        raise HTTPException(
            status_code=422,
            detail="Title and course cannot be empty.",
        )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO assignments (title, course, deadline)
            VALUES (?, ?, ?)
            """,
            (title, course, assignment.deadline),
        )

        row = connection.execute(
            """
            SELECT id, title, course, deadline, completed, created_at
            FROM assignments
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return assignment_to_dict(row)


@app.patch("/api/assignments/{assignment_id}")
def update_assignment(
    assignment_id: int,
    update: AssignmentUpdate,
):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE assignments
            SET completed = ?
            WHERE id = ?
            """,
            (int(update.completed), assignment_id),
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Assignment not found.",
            )

        row = connection.execute(
            """
            SELECT id, title, course, deadline, completed, created_at
            FROM assignments
            WHERE id = ?
            """,
            (assignment_id,),
        ).fetchone()

    return assignment_to_dict(row)


@app.delete(
    "/api/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_assignment(assignment_id: int):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM assignments WHERE id = ?",
            (assignment_id,),
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Assignment not found.",
            )

    return Response(status_code=status.HTTP_204_NO_CONTENT)