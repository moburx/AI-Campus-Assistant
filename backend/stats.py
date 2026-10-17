"""Статистикийн API: самбарт харуулах тоо, график, хичээл тус бүрийн явц."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from backend.auth import get_current_user
from backend.database import get_connection

router = APIRouter(prefix="/api/stats", tags=["stats"])

PRIORITIES = ("high", "medium", "low")


def parse_date(value):
    """'2026-10-17' эсвэл '2026-10-17 06:12:24' хэлбэрээс огноо гаргана."""
    if not value:
        return None

    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def week_start(day: date) -> date:
    """Тухайн өдрийн долоо хоногийн Даваа гараг."""
    return day - timedelta(days=day.weekday())


def build_weekly_completed(rows, today: date, weeks: int):
    """Сүүлийн N долоо хоногт хэдэн даалгавар дуусгасныг тоолно (хуучнаас шинэ рүү)."""
    current_week = week_start(today)
    starts = [
        current_week - timedelta(weeks=offset)
        for offset in range(weeks - 1, -1, -1)
    ]
    counts = {start: 0 for start in starts}

    for row in rows:
        done_day = parse_date(row["completed_at"])
        if row["completed"] and done_day is not None:
            start = week_start(done_day)
            if start in counts:
                counts[start] += 1

    return [
        {"week_start": start.isoformat(), "count": counts[start]}
        for start in starts
    ]


def build_upcoming(rows, today: date, days: int):
    """Ойрын N өдөр (өнөөдрийг оруулаад) өдөр бүр хэдэн даалгаврын хугацаа дуусахыг."""
    dates = [today + timedelta(days=offset) for offset in range(days)]
    counts = {day: 0 for day in dates}

    for row in rows:
        deadline = parse_date(row["deadline"])
        if not row["completed"] and deadline in counts:
            counts[deadline] += 1

    return [
        {"date": day.isoformat(), "count": counts[day]}
        for day in dates
    ]


def build_by_priority(rows):
    result = {priority: {"total": 0, "completed": 0} for priority in PRIORITIES}

    for row in rows:
        priority = row["priority"] if row["priority"] in result else "medium"
        result[priority]["total"] += 1
        if row["completed"]:
            result[priority]["completed"] += 1

    return result


def build_by_course(connection, user_id: int):
    rows = connection.execute(
        """
        SELECT
            c.id,
            c.name,
            c.color,
            COUNT(a.id) AS total,
            COALESCE(SUM(a.completed), 0) AS completed
        FROM courses AS c
        LEFT JOIN assignments AS a
            ON a.course_id = c.id AND a.user_id = c.user_id
        WHERE c.user_id = ?
        GROUP BY c.id
        HAVING COUNT(a.id) > 0
        ORDER BY total DESC, c.name COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "color": row["color"],
            "total": row["total"],
            "completed": row["completed"],
        }
        for row in rows
    ]


@router.get("")
def get_stats(
    weeks: int = Query(default=8, ge=1, le=26),
    current_user: dict = Depends(get_current_user),
):
    today = date.today()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT deadline, completed, completed_at, priority
            FROM assignments
            WHERE user_id = ?
            """,
            (current_user["id"],),
        ).fetchall()

        by_course = build_by_course(connection, current_user["id"])

    total = len(rows)
    completed = sum(1 for row in rows if row["completed"])
    week_end = today + timedelta(days=6)

    overdue = 0
    due_this_week = 0
    for row in rows:
        if row["completed"]:
            continue
        deadline = parse_date(row["deadline"])
        if deadline is None:
            continue
        if deadline < today:
            overdue += 1
        elif deadline <= week_end:
            due_this_week += 1

    return {
        "today": today.isoformat(),
        "total": total,
        "completed": completed,
        "remaining": total - completed,
        "overdue": overdue,
        "due_this_week": due_this_week,
        "completion_rate": round(completed * 100 / total) if total else 0,
        "by_course": by_course,
        "by_priority": build_by_priority(rows),
        "weekly_completed": build_weekly_completed(rows, today, weeks),
        "upcoming": build_upcoming(rows, today, 7),
    }
