import sqlite3

from pwdlib import PasswordHash
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.database import get_connection, init_database
import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing. Check your .env file."
    )

bearer_scheme = HTTPBearer()
def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )

        user_id = int(payload["sub"])

    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT id, username, email, country, preferred_language
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return dict(user)


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
password_hash = PasswordHash.recommended()

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    country: str = Field(default="Other", min_length=1, max_length=50)
    preferred_language: str = Field(
        default="en",
        min_length=2,
        max_length=10,
    )


class UserLogin(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8, max_length=128)

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
def get_assignments(
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, course, deadline, completed, created_at
            FROM assignments
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (current_user["id"],),
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
            INSERT INTO assignments (
                title, course, deadline, user_id
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                title,
                course,
                assignment.deadline,
                current_user["id"],
            ),
        )

        row = connection.execute(
            """
            SELECT id, title, course, deadline, completed, created_at
            FROM assignments
            WHERE id = ? AND user_id = ?
            """,
            (cursor.lastrowid, current_user["id"]),
        ).fetchone()

    return assignment_to_dict(row)


@app.patch("/api/assignments/{assignment_id}")
def update_assignment(
    assignment_id: int,
    update: AssignmentUpdate,
    current_user: dict = Depends(get_current_user),
):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE assignments
            SET completed = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                int(update.completed),
                assignment_id,
                current_user["id"],
            ),
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
            WHERE id = ? AND user_id = ?
            """,
            (assignment_id, current_user["id"]),
        ).fetchone()

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


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate):
    username = user.username.strip()
    email = user.email.strip().lower()
    country = user.country.strip()
    preferred_language = user.preferred_language.strip().lower()

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
