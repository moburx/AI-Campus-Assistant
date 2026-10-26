"""Бүртгүүлэхэд имэйлээр 6 оронтой код илгээж баталгаажуулах."""

from datetime import datetime, timedelta, timezone

import pytest

from backend import mailer, verification
from backend.database import get_connection, init_database
from tests.conftest import DEFAULT_PASSWORD, auth_headers, latest_code
from tests.test_database import create_old_schema


def sign_up(client, username="mina", language="mn", email=None):
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": DEFAULT_PASSWORD,
            "country": "Mongolia",
            "preferred_language": language,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def verify(client, code, username="mina"):
    return client.post("/api/auth/verify", json={"username": username, "code": code})


def login(client, username="mina", password=DEFAULT_PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def wrong_code(code: str) -> str:
    return "000000" if code != "000000" else "111111"


def set_last_sent(username, seconds_ago):
    sent_at = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE email_verifications SET last_sent_at = ?
            WHERE user_id = (SELECT id FROM users WHERE username = ?)
            """,
            (sent_at.isoformat(), username),
        )


# ---------- Бүртгэл ба имэйл ----------
def test_register_sends_code_in_users_language(client):
    data = sign_up(client, language="mn")

    assert data["verification_required"] is True
    assert data["email_sent"] is True
    message = mailer.outbox[-1]
    assert message["To"] == "mina@example.com"
    assert message["Subject"] == "AI Campus баталгаажуулах код"
    assert len(latest_code()) == verification.CODE_LENGTH


def test_code_is_stored_as_hash_not_plain_text(client):
    sign_up(client)
    code = latest_code()

    with get_connection() as connection:
        stored = connection.execute("SELECT code_hash FROM email_verifications").fetchone()["code_hash"]

    assert code not in stored
    assert len(stored) == 64


def test_register_still_works_when_email_fails(client, monkeypatch):
    def broken(*args, **kwargs):
        raise mailer.EmailError("SMTP down")

    monkeypatch.setattr(mailer, "send_email", broken)

    data = sign_up(client)

    assert data["email_sent"] is False
    assert login(client).status_code == 403


# ---------- Нэвтрэх ----------
def test_unverified_user_cannot_log_in(client):
    sign_up(client)

    response = login(client)

    assert response.status_code == 403
    assert response.json()["detail"] == "Email not verified."


def test_wrong_password_hides_verification_state(client):
    sign_up(client)
    assert login(client, password="wrong-password").status_code == 401


# ---------- Код шалгах ----------
def test_correct_code_verifies_and_logs_in(client):
    sign_up(client)

    response = verify(client, latest_code())

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["username"] == "mina"
    assert client.get("/api/auth/me", headers=auth_headers(data["access_token"])).status_code == 200
    assert login(client).status_code == 200
    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM email_verifications").fetchone()[0] == 0


def test_wrong_code_is_rejected(client):
    sign_up(client)

    response = verify(client, wrong_code(latest_code()))

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired code."
    assert login(client).status_code == 403


def test_too_many_wrong_codes_block_even_the_right_one(client):
    sign_up(client)
    code = latest_code()

    for _ in range(verification.MAX_ATTEMPTS):
        assert verify(client, wrong_code(code)).status_code == 400

    response = verify(client, code)
    assert response.status_code == 429


def test_expired_code_is_rejected(client):
    sign_up(client)
    code = latest_code()
    user_id = verification.find_user("mina")["id"]
    later = datetime.now(timezone.utc) + timedelta(minutes=verification.CODE_TTL_MINUTES + 1)

    with pytest.raises(verification.VerificationError):
        verification.check_code(user_id, code, now=later)


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef"])
def test_code_must_be_six_digits(client, code):
    sign_up(client)
    assert verify(client, code).status_code == 422


def test_unknown_or_verified_user_gets_same_error(client):
    assert verify(client, "123456", username="nobody").status_code == 400

    sign_up(client)
    verify(client, latest_code())
    assert verify(client, "123456").status_code == 400


# ---------- Дахин илгээх ----------
def test_resend_has_a_cooldown(client):
    sign_up(client)

    response = client.post("/api/auth/resend", json={"username": "mina"})

    assert response.status_code == 429
    assert 0 < int(response.headers["Retry-After"]) <= verification.RESEND_COOLDOWN_SECONDS


def test_resend_after_cooldown_replaces_the_old_code(client):
    sign_up(client)
    old_code = latest_code()
    set_last_sent("mina", verification.RESEND_COOLDOWN_SECONDS + 1)

    response = client.post("/api/auth/resend", json={"username": "mina"})

    assert response.status_code == 200
    assert len(mailer.outbox) == 2
    new_code = latest_code()
    if new_code != old_code:
        assert verify(client, old_code).status_code == 400
    assert verify(client, new_code).status_code == 200


def test_resend_resets_attempts(client):
    sign_up(client)
    for _ in range(verification.MAX_ATTEMPTS):
        verify(client, wrong_code(latest_code()))
    set_last_sent("mina", verification.RESEND_COOLDOWN_SECONDS + 1)

    client.post("/api/auth/resend", json={"username": "mina"})

    assert verify(client, latest_code()).status_code == 200


def test_resend_does_not_reveal_unknown_users(client):
    response = client.post("/api/auth/resend", json={"username": "nobody"})

    assert response.status_code == 200
    assert mailer.outbox == []


# ---------- Хуучин хэрэглэгчид ----------
def test_existing_users_count_as_verified_after_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "old.db"
    create_old_schema(db_path)
    monkeypatch.setenv("CAMPUS_DB_PATH", str(db_path))

    init_database()

    with get_connection() as connection:
        row = connection.execute("SELECT email_verified FROM users WHERE username = 'old'").fetchone()
    assert row["email_verified"] == 1


@pytest.mark.parametrize("language", ["ko", "mn", "zh", "ru", "vi", "en"])
def test_email_text_exists_for_every_language(language):
    subject, body = verification.build_email(language, "123456")
    assert subject
    assert "123456" in body
    assert str(verification.CODE_TTL_MINUTES) in body
