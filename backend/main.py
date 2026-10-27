import sqlite3
from contextlib import asynccontextmanager
from typing import Optional

from pathlib import Path
from fastapi.staticfiles import StaticFiles

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from backend import assignments, assistant, courses, mailer, notices_api, reminders, stats, verification
from backend.assignments import clean_text
from backend.auth import (
    LanguageCode,
    create_access_token,
    get_current_user,
    get_user_by_id,
    password_hash,
)
from backend.database import get_connection, init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    # Дуусах хугацааны сануулгыг арын thread-д шалгана (REMINDERS_ENABLED=0 бол ажиллахгүй).
    reminders.start_background_reminders()
    yield
    reminders.stop_background_reminders()


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

@app.middleware("http")
async def no_cache_for_frontend(request, call_next):
    """Frontend файлыг browser кэшлэх үедээ сервертэй заавал тулгадаг болгоно.

    Өөрчлөгдөөгүй бол 304 (хурдан), өөрчлөгдсөн бол шинэ файлыг авна.
    Ингэснээр хуучин app.js, i18n.js ачаалагдах асуудал гарахгүй.
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache"
    return response

app.include_router(assignments.router)
app.include_router(courses.router)
app.include_router(stats.router)
app.include_router(assistant.router)
app.include_router(notices_api.router)
app.include_router(verification.router)


# ---------- Загварууд ----------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    country: str = Field(default="Other", min_length=1, max_length=50)
    preferred_language: LanguageCode = "en"


class UserLogin(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    country: Optional[str] = Field(default=None, min_length=1, max_length=50)
    preferred_language: Optional[LanguageCode] = None
    reminders_enabled: Optional[bool] = None


# ---------- Ерөнхий ----------
@app.get("/api")
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
    email = str(user.email).strip().lower()
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
                    preferred_language,
                    email_verified
                )
                VALUES (?, ?, ?, ?, ?, 0)
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

    # Баталгаажуулах код илгээнэ. Имэйл явахгүй байсан ч бүртгэл үлдэнэ,
    # хэрэглэгч "код дахин илгээх"-ээр дахин оролдож болно.
    email_sent = True
    try:
        verification.send_code(verification.find_user(username))
    except mailer.EmailError as error:
        print("verification email error:", error)
        email_sent = False

    return {
        "id": user_id,
        "username": username,
        "email": email,
        "country": country,
        "preferred_language": preferred_language,
        "verification_required": True,
        "email_sent": email_sent,
        "message": "Registration successful. Check your email for the code.",
    }


@app.post("/api/auth/login")
def login_user(user: UserLogin):
    username = user.username.strip()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, username, email, password_hash,
                   country, preferred_language, email_verified, reminders_enabled
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

    # Нууц үг зөв үед л хэлнэ (нууц үггүйгээр акаунтын төлөв илрэхгүй).
    if not row["email_verified"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified.",
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
            "reminders_enabled": bool(row["reminders_enabled"]),
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

    if update.reminders_enabled is not None:
        changes["reminders_enabled"] = int(update.reminders_enabled)

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
# ---------- Frontend ----------
# API-ийн бүх замыг бүртгэсний ДАРАА холбоно. Ингэснээр /api/... хүсэлтүүд
# эхлээд API руу очиж, бусад зам (/, /app.js, /style.css ...) frontend файл болно.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")