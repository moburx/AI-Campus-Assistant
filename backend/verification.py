"""Бүртгүүлэхэд имэйлээр 6 оронтой код илгээж баталгаажуулах.

Урсгал:
  1. POST /api/auth/register  → хэрэглэгч email_verified=0 төлөвтэй үүснэ, код имэйлээр очно
  2. POST /api/auth/verify    → зөв код оруулбал баталгаажиж, шууд нэвтэрнэ (token буцаана)
  3. POST /api/auth/resend    → код дахин илгээх (60 секундэд нэг удаа)
  Баталгаажаагүй хэрэглэгч нэвтэрвэл 403 "Email not verified." буцаана.

Аюулгүй байдал:
  - Кодыг DB-д шууд биш, HMAC-SHA256 hash-аар хадгална.
  - Код 10 минут хүчинтэй, буруу 5 удаа оруулбал хүчингүй болно.
  - resend нь хэрэглэгч байгаа эсэхийг илчлэхгүй (үргэлж ижил хариу).
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend import mailer
from backend.auth import create_access_token
from backend.database import get_connection

CODE_LENGTH = 6
CODE_TTL_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60

router = APIRouter(prefix="/api/auth", tags=["verification"])

EMAIL_TEXT = {
    "ko": ("AI Campus 인증 코드", "AI Campus 인증 코드: {code}\n\n{minutes}분 동안 유효합니다.\n직접 요청하지 않았다면 이 메일을 무시하세요."),
    "mn": ("AI Campus баталгаажуулах код", "AI Campus баталгаажуулах код: {code}\n\n{minutes} минут хүчинтэй.\nХэрэв та бүртгүүлээгүй бол энэ имэйлийг үл тоомсорлоорой."),
    "zh": ("AI Campus 验证码", "AI Campus 验证码：{code}\n\n{minutes} 分钟内有效。\n如果不是您本人操作，请忽略此邮件。"),
    "ru": ("Код подтверждения AI Campus", "Код подтверждения AI Campus: {code}\n\nДействует {minutes} минут.\nЕсли вы не регистрировались, просто проигнорируйте это письмо."),
    "vi": ("Mã xác minh AI Campus", "Mã xác minh AI Campus: {code}\n\nCó hiệu lực trong {minutes} phút.\nNếu bạn không đăng ký, hãy bỏ qua email này."),
    "en": ("Your AI Campus verification code", "Your AI Campus verification code: {code}\n\nIt is valid for {minutes} minutes.\nIf you did not sign up, you can ignore this email."),
}


class VerificationError(Exception):
    """Код буруу, хугацаа дууссан эсвэл оролдлого хэтэрсэн."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class VerifyRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    code: str = Field(min_length=CODE_LENGTH, max_length=CODE_LENGTH, pattern=r"^\d+$")


class ResendRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_code() -> str:
    return str(secrets.randbelow(10 ** CODE_LENGTH)).zfill(CODE_LENGTH)


def hash_code(user_id: int, code: str) -> str:
    # Код ердөө 6 оронтой тул JWT нууц түлхүүрээр "давс" нэмж hash хийнэ.
    secret = os.getenv("JWT_SECRET_KEY", "").encode()
    return hmac.new(secret, f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def find_user(username: str):
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT id, username, email, country, preferred_language, email_verified
            FROM users WHERE username = ?
            """,
            (username.strip(),),
        ).fetchone()


def build_email(language: str, code: str) -> tuple:
    subject, body = EMAIL_TEXT.get(language, EMAIL_TEXT["en"])
    return subject, body.format(code=code, minutes=CODE_TTL_MINUTES)


def send_code(user, now: datetime = None) -> None:
    """Шинэ код үүсгэж хадгалаад имэйлээр илгээнэ (өмнөх кодыг солино)."""
    now = now or utc_now()
    code = generate_code()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO email_verifications (user_id, code_hash, expires_at, attempts, last_sent_at)
            VALUES (?, ?, ?, 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                code_hash = excluded.code_hash,
                expires_at = excluded.expires_at,
                attempts = 0,
                last_sent_at = excluded.last_sent_at
            """,
            (
                user["id"],
                hash_code(user["id"], code),
                (now + timedelta(minutes=CODE_TTL_MINUTES)).isoformat(),
                now.isoformat(),
            ),
        )

    subject, body = build_email(user["preferred_language"], code)
    mailer.send_email(user["email"], subject, body)


def seconds_until_resend(user_id: int, now: datetime = None) -> int:
    now = now or utc_now()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT last_sent_at FROM email_verifications WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    if row is None:
        return 0

    elapsed = (now - datetime.fromisoformat(row["last_sent_at"])).total_seconds()
    return max(0, int(RESEND_COOLDOWN_SECONDS - elapsed + 0.999))


def check_code(user_id: int, code: str, now: datetime = None) -> None:
    """Код зөв бол баталгаажуулна. Буруу бол VerificationError шиднэ."""
    now = now or utc_now()

    with get_connection() as connection:
        row = connection.execute(
            "SELECT code_hash, expires_at, attempts FROM email_verifications WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            raise VerificationError("Invalid or expired code.")

        if now > datetime.fromisoformat(row["expires_at"]):
            raise VerificationError("Invalid or expired code.")

        if row["attempts"] >= MAX_ATTEMPTS:
            raise VerificationError(
                "Too many attempts. Request a new code.",
                status.HTTP_429_TOO_MANY_REQUESTS,
            )

        is_correct = hmac.compare_digest(row["code_hash"], hash_code(user_id, code))
        if is_correct:
            connection.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user_id,))
            connection.execute("DELETE FROM email_verifications WHERE user_id = ?", (user_id,))
        else:
            connection.execute(
                "UPDATE email_verifications SET attempts = attempts + 1 WHERE user_id = ?",
                (user_id,),
            )

    # with блок дотор алдаа шидвэл SQLite өөрчлөлтийг буцаадаг (rollback).
    # Тиймээс оролдлогын тоог хадгалсны ДАРАА алдаа шиднэ.
    if not is_correct:
        raise VerificationError("Invalid or expired code.")


def public_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "country": row["country"],
        "preferred_language": row["preferred_language"],
    }


@router.post("/verify")
def verify_email(request: VerifyRequest):
    user = find_user(request.username)

    # Хэрэглэгч байхгүй эсвэл аль хэдийн баталгаажсан бол ижил алдаа (мэдээлэл задруулахгүй).
    if user is None or user["email_verified"]:
        raise HTTPException(status_code=400, detail="Invalid or expired code.")

    try:
        check_code(user["id"], request.code)
    except VerificationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)

    return {
        "access_token": create_access_token(user["id"]),
        "token_type": "bearer",
        "user": public_user(user),
        "message": "Email verified.",
    }


@router.post("/resend")
def resend_code(request: ResendRequest):
    user = find_user(request.username)

    if user is not None and not user["email_verified"]:
        wait = seconds_until_resend(user["id"])
        if wait > 0:
            raise HTTPException(
                status_code=429,
                detail="Please wait before requesting a new code.",
                headers={"Retry-After": str(wait)},
            )
        try:
            send_code(user)
        except mailer.EmailError as error:
            print("verification email error:", error)
            raise HTTPException(status_code=503, detail="Could not send the email.")

    return {"sent": True, "retry_after": RESEND_COOLDOWN_SECONDS}
