"""Бүртгэл, нэвтрэлт, JWT, хэрэглэгчийн тохиргооны тест."""

import jwt
import pytest
from datetime import datetime, timedelta, timezone

from backend.auth import JWT_ALGORITHM, JWT_SECRET_KEY
from tests.conftest import auth_headers, login, register


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_returns_user_without_password(client):
    data = register(client, "alice", language="ko")

    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert data["preferred_language"] == "ko"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_lowercases_email(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "bob",
            "email": "Bob@Example.COM",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    assert response.json()["email"] == "bob@example.com"


def test_register_duplicate_username_returns_409(client):
    register(client, "alice")

    response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "other@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 409


def test_register_duplicate_email_returns_409(client):
    register(client, "alice")

    response = client.post(
        "/api/auth/register",
        json={
            "username": "alice2",
            "email": "alice@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 409


def test_register_short_password_returns_422(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "carol",
            "email": "carol@example.com",
            "password": "short",
        },
    )
    assert response.status_code == 422


def test_register_unsupported_language_returns_422(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "dave",
            "email": "dave@example.com",
            "password": "password123",
            "preferred_language": "xx",
        },
    )
    assert response.status_code == 422


def test_login_success_returns_token_and_user(client):
    register(client, "alice")

    response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    data = response.json()

    assert response.status_code == 200
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["username"] == "alice"


def test_login_wrong_password_returns_401(client):
    register(client, "alice")

    response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_login_unknown_user_returns_401(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "password123"},
    )
    assert response.status_code == 401


def test_password_is_stored_hashed(client):
    from backend.database import get_connection

    register(client, "alice")

    with get_connection() as connection:
        stored = connection.execute(
            "SELECT password_hash FROM users WHERE username = 'alice'"
        ).fetchone()["password_hash"]

    assert stored != "password123"
    assert "password123" not in stored


def test_me_requires_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code in (401, 403)


def test_me_with_valid_token(client):
    register(client, "alice")
    token = login(client, "alice")

    response = client.get("/api/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_invalid_token_returns_401(client):
    response = client.get(
        "/api/auth/me",
        headers=auth_headers("not-a-real-token"),
    )
    assert response.status_code == 401


def test_expired_token_returns_401(client):
    user = register(client, "alice")
    expired = jwt.encode(
        {
            "sub": str(user["id"]),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )

    response = client.get("/api/auth/me", headers=auth_headers(expired))
    assert response.status_code == 401


def test_token_signed_with_other_key_returns_401(client):
    user = register(client, "alice")
    forged = jwt.encode(
        {
            "sub": str(user["id"]),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "a-completely-different-secret-key-for-forging-tokens",
        algorithm="HS256",
    )

    response = client.get("/api/auth/me", headers=auth_headers(forged))
    assert response.status_code == 401


def test_update_language(client, user_headers):
    response = client.patch(
        "/api/auth/me",
        json={"preferred_language": "vi"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["preferred_language"] == "vi"
    assert client.get("/api/auth/me", headers=user_headers).json()[
        "preferred_language"
    ] == "vi"


def test_update_language_rejects_unknown_code(client, user_headers):
    response = client.patch(
        "/api/auth/me",
        json={"preferred_language": "fr"},
        headers=user_headers,
    )
    assert response.status_code == 422


def test_update_me_with_empty_body_returns_422(client, user_headers):
    response = client.patch("/api/auth/me", json={}, headers=user_headers)
    assert response.status_code == 422

@pytest.mark.parametrize(
    "email",
    ["aaaaa", "no-at-sign.com", "user@", "@example.com", "two words@example.com"],
)
def test_register_invalid_email_returns_422(client, email):
    response = client.post(
        "/api/auth/register",
        json={"username": "erin", "email": email, "password": "password123"},
    )
    assert response.status_code == 422