"""Дуусах хугацааны имэйл сануулга (D-1, D-day)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend import mailer, reminders
from backend.database import get_connection

SEOUL = ZoneInfo("Asia/Seoul")
MORNING = datetime(2026, 10, 27, 9, 30, tzinfo=SEOUL)
TODAY = MORNING.date().isoformat()
TOMORROW = (MORNING.date() + timedelta(days=1)).isoformat()


def run(now=MORNING, **kwargs):
    return reminders.send_due_reminders(now=now, **kwargs)


def body_of(message) -> str:
    return message.get_body(("plain",)).get_content()


@pytest.fixture(autouse=True)
def morning_hour(monkeypatch):
    monkeypatch.setenv("REMINDER_HOUR", "9")


# ---------- Илгээх ----------
def test_one_email_lists_today_and_tomorrow(client, make_user, create_assignment):
    headers = make_user("mina", language="mn")
    mailer.outbox.clear()
    create_assignment(headers, title="IoT тайлан", course="IoT", deadline=TODAY)
    create_assignment(headers, title="CV лаб", course="CV", deadline=TOMORROW)
    create_assignment(headers, title="Хол", course="CV", deadline="2030-01-01")

    assert run() == {"sent": 1, "failed": 0}

    assert len(mailer.outbox) == 1
    message = mailer.outbox[0]
    assert message["To"] == "mina@example.com"
    assert message["Subject"] == "AI Campus сануулга: 2 даалгавар"
    body = body_of(message)
    assert "Өнөөдөр дуусна" in body and "IoT тайлан [IoT]" in body
    assert "Маргааш дуусна" in body and "CV лаб [CV]" in body
    assert "Хол" not in body
    assert body.index("IoT тайлан") < body.index("CV лаб")


def test_each_user_gets_only_their_own_assignments(client, make_user, create_assignment):
    alice = make_user("alice", language="en")
    bob = make_user("bobby", language="ko")
    mailer.outbox.clear()
    create_assignment(alice, title="Alice essay", deadline=TOMORROW)
    create_assignment(bob, title="Bob report", deadline=TOMORROW)

    assert run()["sent"] == 2

    by_recipient = {message["To"]: body_of(message) for message in mailer.outbox}
    assert "Alice essay" in by_recipient["alice@example.com"]
    assert "Bob report" not in by_recipient["alice@example.com"]
    assert "내일 마감" in by_recipient["bobby@example.com"]


def test_nothing_due_sends_nothing(client, user_headers, create_assignment):
    mailer.outbox.clear()
    create_assignment(user_headers, deadline="2030-01-01")

    assert run() == {"sent": 0, "failed": 0}
    assert mailer.outbox == []


# ---------- Давхардахгүй ----------
def test_same_reminder_is_not_sent_twice(client, user_headers, create_assignment):
    mailer.outbox.clear()
    create_assignment(user_headers, deadline=TOMORROW)

    assert run()["sent"] == 1
    assert run(now=MORNING + timedelta(hours=3))["sent"] == 0
    assert len(mailer.outbox) == 1


def test_tomorrow_reminder_then_today_reminder(client, user_headers, create_assignment):
    mailer.outbox.clear()
    create_assignment(user_headers, title="Quiz", deadline=TOMORROW)

    run()
    run(now=MORNING + timedelta(days=1))

    assert len(mailer.outbox) == 2
    assert "Due tomorrow" in body_of(mailer.outbox[0])
    assert "Due today" in body_of(mailer.outbox[1])


def test_changed_deadline_is_reminded_again(client, user_headers, create_assignment):
    mailer.outbox.clear()
    item = create_assignment(user_headers, deadline=TOMORROW)
    run()

    client.patch(f"/api/assignments/{item['id']}", json={"deadline": TODAY}, headers=user_headers)
    run(now=MORNING + timedelta(hours=1))
    client.patch(f"/api/assignments/{item['id']}", json={"deadline": TOMORROW}, headers=user_headers)
    run(now=MORNING + timedelta(hours=2))

    # Маргааш → өнөөдөр болгосон: дахин сануулна. Буцааж маргааш болгосон: аль хэдийн сануулсан.
    assert len(mailer.outbox) == 2


# ---------- Хэнд илгээхгүй вэ ----------
def test_completed_and_overdue_are_skipped(client, user_headers, create_assignment):
    mailer.outbox.clear()
    done = create_assignment(user_headers, title="Done", deadline=TOMORROW)
    client.patch(f"/api/assignments/{done['id']}", json={"completed": True}, headers=user_headers)
    create_assignment(user_headers, title="Late", deadline="2026-10-20")

    assert run()["sent"] == 0


def test_user_can_turn_reminders_off(client, user_headers, create_assignment):
    mailer.outbox.clear()
    create_assignment(user_headers, deadline=TOMORROW)

    response = client.patch("/api/auth/me", json={"reminders_enabled": False}, headers=user_headers)

    assert response.status_code == 200
    assert response.json()["reminders_enabled"] is False
    assert client.get("/api/auth/me", headers=user_headers).json()["reminders_enabled"] is False
    assert run()["sent"] == 0


def test_reminders_are_on_by_default(client, user_headers):
    assert client.get("/api/auth/me", headers=user_headers).json()["reminders_enabled"] is True


def test_unverified_users_get_no_reminders(client, user_headers, create_assignment):
    mailer.outbox.clear()
    create_assignment(user_headers, deadline=TOMORROW)
    with get_connection() as connection:
        connection.execute("UPDATE users SET email_verified = 0")

    assert run()["sent"] == 0


# ---------- Цаг ----------
def test_waits_until_reminder_hour(client, user_headers, create_assignment):
    mailer.outbox.clear()
    create_assignment(user_headers, deadline=TOMORROW)
    early = MORNING.replace(hour=7)

    assert run(now=early)["sent"] == 0
    assert run(now=early, force=True)["sent"] == 1


def test_bad_reminder_hour_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("REMINDER_HOUR", "nine")
    assert reminders.reminder_hour() == reminders.DEFAULT_REMINDER_HOUR


# ---------- Алдаа ----------
def test_failed_email_is_retried_next_time(client, user_headers, create_assignment, monkeypatch):
    mailer.outbox.clear()
    create_assignment(user_headers, deadline=TOMORROW)
    real_send = mailer.send_email

    def broken(*args, **kwargs):
        raise mailer.EmailError("SMTP down")

    monkeypatch.setattr(mailer, "send_email", broken)
    assert run() == {"sent": 0, "failed": 1}

    monkeypatch.setattr(mailer, "send_email", real_send)
    assert run(now=MORNING + timedelta(minutes=30)) == {"sent": 1, "failed": 0}


def test_deleting_assignment_removes_its_reminder_rows(client, user_headers, create_assignment):
    item = create_assignment(user_headers, deadline=TOMORROW)
    run()

    client.delete(f"/api/assignments/{item['id']}", headers=user_headers)

    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM deadline_reminders").fetchone()[0] == 0


# ---------- Арын thread ----------
def test_background_thread_is_off_in_tests():
    assert reminders.reminders_enabled() is False
    assert reminders.start_background_reminders() is False


@pytest.mark.parametrize("language", ["ko", "mn", "zh", "ru", "vi", "en"])
def test_email_text_for_every_language(language):
    items = [{"kind": reminders.KIND_TOMORROW, "deadline": TOMORROW, "title": "T", "course": "C"}]
    subject, body = reminders.build_email(language, items)
    assert "1" in subject
    assert "T [C]" in body
