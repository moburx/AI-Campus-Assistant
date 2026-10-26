"""pytest-ийн нийтлэг тохиргоо.

Тест бүр тусдаа түр зуурын SQLite файл ашиглана. Ингэснээр жинхэнэ
campus.db-д нөлөөлөхгүй, тестүүд бие биеэсээ хамааралгүй ажиллана.
"""

import os
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# backend.auth-ийг import хийхээс өмнө тохируулах ёстой.
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-secret-key-that-is-long-enough-for-hs256-signing",
)

from fastapi.testclient import TestClient  # noqa: E402

from backend import gemini_models, mailer  # noqa: E402
from backend.main import app  # noqa: E402

DEFAULT_PASSWORD = "password123"


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Тест бүрт шинэ DB, AI түлхүүргүй орчин."""
    monkeypatch.setenv("CAMPUS_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Жинхэнэ .env-д EMAIL_MODE=smtp байсан ч тест имэйл илгээхгүй.
    monkeypatch.setenv("EMAIL_MODE", "console")
    # Gemini model-ийн жагсаалт болон "хязгаар дууссан" тэмдэглэгээ тест бүрт шинэ.
    monkeypatch.delenv("GEMINI_MODELS", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    gemini_models.reset_exhausted()
    mailer.outbox.clear()
    yield


@pytest.fixture
def client():
    # with ашигласнаар lifespan (init_database) ажиллана.
    with TestClient(app) as test_client:
        yield test_client


def register(client, username, language="en", password=DEFAULT_PASSWORD):
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
            "country": "Korea",
            "preferred_language": language,
        },
    )
    assert response.status_code == 201, response.text
    # Имэйлээр ирсэн кодоор баталгаажуулна (EMAIL_MODE=console → mailer.outbox).
    verify_email(client, username)
    return response.json()


def latest_code() -> str:
    body = mailer.outbox[-1].get_body(("plain",)).get_content()
    return re.search(r"\b(\d{6})\b", body).group(1)


def verify_email(client, username):
    response = client.post(
        "/api/auth/verify",
        json={"username": username, "code": latest_code()},
    )
    assert response.status_code == 200, response.text
    return response.json()


def login(client, username, password=DEFAULT_PASSWORD):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_user(client):
    """Хэрэглэгч бүртгүүлээд нэвтэрсэн header буцаана."""

    def _make_user(username="student01", language="en"):
        register(client, username, language)
        return auth_headers(login(client, username))

    return _make_user


@pytest.fixture
def user_headers(make_user):
    return make_user()


@pytest.fixture
def create_assignment(client):
    """Даалгавар үүсгээд хариуг буцаана."""

    def _create(headers, **overrides):
        payload = {
            "title": "Python lab",
            "course": "Programming",
            "deadline": "2030-01-15",
        }
        payload.update(overrides)
        response = client.post("/api/assignments", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        return response.json()

    return _create
