"""JWT нэвтрэлт, нууц үгийн hash болон одоогийн хэрэглэгчийг авах функцууд."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from backend.database import get_connection

# Төслийн root дахь .env-ийг бүтэн замаар нь уншина.
# load_dotenv()-ийг замгүй дуудвал backend/ folder-оос эхэлж хайдаг тул
# өөр .env файл олдож, GEMINI_API_KEY уншигдахгүй байх алдаа гарч байсан.
PROJECT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(PROJECT_ENV_FILE)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing. Check your .env file."
    )

# Апп-ын дэмждэг хэлнүүд (frontend-ийн i18n.js-тэй ижил байх ёстой).
SUPPORTED_LANGUAGES = ("ko", "mn", "zh", "ru", "vi", "en")
LanguageCode = Literal["ko", "mn", "zh", "ru", "vi", "en"]

password_hash = PasswordHash.recommended()
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


def get_user_by_id(user_id: int):
    with get_connection() as connection:
        user = connection.execute(
            """
            SELECT id, username, email, country, preferred_language, reminders_enabled
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if user is None:
        return None

    data = dict(user)
    data["reminders_enabled"] = bool(data["reminders_enabled"])
    return data


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

    user = get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
