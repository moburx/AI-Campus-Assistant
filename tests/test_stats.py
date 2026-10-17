"""Статистикийн API-ийн тест."""

from datetime import date, timedelta

from backend.stats import build_weekly_completed, week_start


def days_from_today(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def test_empty_stats(client, user_headers):
    data = client.get("/api/stats", headers=user_headers).json()

    assert data["total"] == 0
    assert data["completed"] == 0
    assert data["completion_rate"] == 0
    assert data["by_course"] == []
    assert len(data["weekly_completed"]) == 8
    assert len(data["upcoming"]) == 7


def test_stats_counts(client, user_headers, create_assignment):
    create_assignment(user_headers, title="Overdue", deadline=days_from_today(-3))
    create_assignment(user_headers, title="Soon", deadline=days_from_today(2), priority="high")
    create_assignment(user_headers, title="Later", deadline=days_from_today(30), priority="low")
    done = create_assignment(user_headers, title="Done", deadline=days_from_today(1))
    client.patch(
        f"/api/assignments/{done['id']}",
        json={"completed": True},
        headers=user_headers,
    )

    data = client.get("/api/stats", headers=user_headers).json()

    assert data["total"] == 4
    assert data["completed"] == 1
    assert data["remaining"] == 3
    assert data["overdue"] == 1
    assert data["due_this_week"] == 1
    assert data["completion_rate"] == 25
    assert data["by_priority"]["high"] == {"total": 1, "completed": 0}
    assert data["by_priority"]["low"] == {"total": 1, "completed": 0}
    assert data["by_priority"]["medium"] == {"total": 2, "completed": 1}


def test_completed_this_week_appears_in_last_bucket(client, user_headers, create_assignment):
    assignment = create_assignment(user_headers)
    client.patch(
        f"/api/assignments/{assignment['id']}",
        json={"completed": True},
        headers=user_headers,
    )

    weekly = client.get("/api/stats", headers=user_headers).json()["weekly_completed"]

    # completed_at нь UTC тул долоо хоногийн хил дээр өмнөх долоо хоногт орж болно.
    assert sum(item["count"] for item in weekly[-2:]) == 1


def test_upcoming_counts_by_day(client, user_headers, create_assignment):
    create_assignment(user_headers, deadline=days_from_today(0))
    create_assignment(user_headers, deadline=days_from_today(0))
    create_assignment(user_headers, deadline=days_from_today(3))

    upcoming = client.get("/api/stats", headers=user_headers).json()["upcoming"]

    assert upcoming[0] == {"date": days_from_today(0), "count": 2}
    assert upcoming[3] == {"date": days_from_today(3), "count": 1}


def test_stats_by_course(client, user_headers, create_assignment):
    create_assignment(user_headers, course="Math")
    create_assignment(user_headers, course="Math")
    create_assignment(user_headers, course="Art")

    by_course = client.get("/api/stats", headers=user_headers).json()["by_course"]

    assert [item["name"] for item in by_course] == ["Math", "Art"]
    assert by_course[0]["total"] == 2


def test_stats_weeks_parameter(client, user_headers):
    data = client.get("/api/stats?weeks=4", headers=user_headers).json()
    assert len(data["weekly_completed"]) == 4

    assert client.get("/api/stats?weeks=0", headers=user_headers).status_code == 422


def test_stats_are_private(client, make_user, create_assignment):
    alice = make_user("alice")
    bob = make_user("bob")
    create_assignment(alice)

    assert client.get("/api/stats", headers=bob).json()["total"] == 0


def test_week_start_is_monday():
    sunday = date(2026, 10, 18)
    assert week_start(sunday) == date(2026, 10, 12)
    assert week_start(date(2026, 10, 12)) == date(2026, 10, 12)


def test_build_weekly_completed_ignores_old_and_open_items():
    today = date(2026, 10, 17)
    rows = [
        {"completed": 1, "completed_at": "2026-10-16 10:00:00"},
        {"completed": 1, "completed_at": "2026-10-06 10:00:00"},
        {"completed": 1, "completed_at": "2025-01-01 10:00:00"},
        {"completed": 0, "completed_at": None},
    ]

    weekly = build_weekly_completed(rows, today, 2)

    assert weekly == [
        {"week_start": "2026-10-05", "count": 1},
        {"week_start": "2026-10-12", "count": 1},
    ]
