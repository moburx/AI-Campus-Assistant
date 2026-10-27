"""Дуусах хугацааны сануулга: маргааш (D-1) болон өнөөдөр (D-day) дуусах даалгаврыг имэйлээр сануулна.

Ажиллах зарчим:
  - Server ажиллаж байх хооронд арын thread REMINDER_CHECK_MINUTES тутамд шалгана.
  - Өглөө REMINDER_HOUR цагаас хойш (Солонгосын цагаар) хэрэглэгч бүрт ӨДӨРТ НЭГ имэйл:
    "Өнөөдөр дуусах: ..., Маргааш дуусах: ..."
  - Нэг даалгаврыг нэг төрлөөр (D-1 / D-day) нэг л удаа сануулна (deadline_reminders хүснэгт).
    Хугацааг өөрчилбөл шинэ хугацаагаар дахин сануулна.
  - Зөвхөн имэйлээ баталгаажуулсан, сануулга асаасан хэрэглэгчид.

.env:
    REMINDERS_ENABLED=1        # 0 бол арын thread ажиллахгүй
    REMINDER_HOUR=9            # хэдэн цагаас хойш илгээх
    APP_TIMEZONE=Asia/Seoul

Гараар нэг удаа ажиллуулах (туршихад): python -m backend.reminders
"""

import os
import sys
import threading
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from backend import mailer
from backend.database import get_connection

REMINDER_CHECK_MINUTES = 30
DEFAULT_REMINDER_HOUR = 9

KIND_TODAY = "d0"
KIND_TOMORROW = "d1"

EMAIL_TEXT = {
    "ko": {
        "subject": "AI Campus 마감 알림: {n}개",
        "today": "오늘 마감",
        "tomorrow": "내일 마감",
        "footer": "앱에서 알림을 끌 수 있어요.",
    },
    "mn": {
        "subject": "AI Campus сануулга: {n} даалгавар",
        "today": "Өнөөдөр дуусна",
        "tomorrow": "Маргааш дуусна",
        "footer": "Сануулгыг апп дотроос унтрааж болно.",
    },
    "zh": {
        "subject": "AI Campus 截止提醒：{n} 项",
        "today": "今天截止",
        "tomorrow": "明天截止",
        "footer": "可以在应用中关闭提醒。",
    },
    "ru": {
        "subject": "AI Campus: напоминание о {n} заданиях",
        "today": "Срок сегодня",
        "tomorrow": "Срок завтра",
        "footer": "Напоминания можно отключить в приложении.",
    },
    "vi": {
        "subject": "AI Campus nhắc hạn: {n} bài tập",
        "today": "Hết hạn hôm nay",
        "tomorrow": "Hết hạn ngày mai",
        "footer": "Bạn có thể tắt nhắc nhở trong ứng dụng.",
    },
    "en": {
        "subject": "AI Campus reminder: {n} due soon",
        "today": "Due today",
        "tomorrow": "Due tomorrow",
        "footer": "You can turn reminders off in the app.",
    },
}


def app_timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Seoul"))


def reminder_hour() -> int:
    try:
        return min(23, max(0, int(os.getenv("REMINDER_HOUR", DEFAULT_REMINDER_HOUR))))
    except ValueError:
        return DEFAULT_REMINDER_HOUR


def local_now() -> datetime:
    return datetime.now(app_timezone())


def find_due_assignments(today: date) -> list:
    """Сануулах ёстой (өмнө нь сануулаагүй) даалгавруудыг хэрэглэгчийн мэдээлэлтэй нь."""
    tomorrow = today + timedelta(days=1)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT a.id, a.title, a.course, a.deadline, a.priority,
                   u.id AS user_id, u.email, u.preferred_language,
                   CASE WHEN a.deadline = :today THEN :kind_today ELSE :kind_tomorrow END AS kind
            FROM assignments a
            JOIN users u ON u.id = a.user_id
            WHERE a.completed = 0
              AND a.deadline IN (:today, :tomorrow)
              AND u.email_verified = 1
              AND u.reminders_enabled = 1
              AND NOT EXISTS (
                  SELECT 1 FROM deadline_reminders r
                  WHERE r.assignment_id = a.id
                    AND r.deadline = a.deadline
                    AND r.kind = CASE WHEN a.deadline = :today THEN :kind_today ELSE :kind_tomorrow END
              )
            ORDER BY u.id, a.deadline, a.title
            """,
            {
                "today": today.isoformat(),
                "tomorrow": tomorrow.isoformat(),
                "kind_today": KIND_TODAY,
                "kind_tomorrow": KIND_TOMORROW,
            },
        ).fetchall()

    return [dict(row) for row in rows]


def group_by_user(rows: list) -> dict:
    users = {}
    for row in rows:
        users.setdefault(row["user_id"], []).append(row)
    return users


def build_email(language: str, items: list) -> tuple:
    text = EMAIL_TEXT.get(language, EMAIL_TEXT["en"])
    lines = []

    for kind, label in ((KIND_TODAY, text["today"]), (KIND_TOMORROW, text["tomorrow"])):
        section = [item for item in items if item["kind"] == kind]
        if not section:
            continue
        lines.append(f"{label} ({section[0]['deadline']})")
        lines.extend(f"  - {item['title']} [{item['course']}]" for item in section)
        lines.append("")

    lines.append(text["footer"])
    return text["subject"].format(n=len(items)), "\n".join(lines)


def mark_sent(items: list, sent_at: str) -> None:
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT OR IGNORE INTO deadline_reminders (assignment_id, kind, deadline, sent_at)
            VALUES (?, ?, ?, ?)
            """,
            [(item["id"], item["kind"], item["deadline"], sent_at) for item in items],
        )


def send_due_reminders(now: datetime = None, force: bool = False) -> dict:
    """Нэг удаа шалгаж илгээнэ. force=True бол REMINDER_HOUR-ыг хүлээхгүй."""
    now = now or local_now()

    if not force and now.hour < reminder_hour():
        return {"sent": 0, "failed": 0, "skipped": "too early"}

    sent = failed = 0
    for user_items in group_by_user(find_due_assignments(now.date())).values():
        first = user_items[0]
        subject, body = build_email(first["preferred_language"], user_items)
        try:
            mailer.send_email(first["email"], subject, body)
        except mailer.EmailError as error:
            # Тэмдэглэхгүй: дараагийн шалгалтаар дахин оролдоно.
            print("reminder email error:", error)
            failed += 1
            continue

        mark_sent(user_items, now.isoformat())
        sent += 1

    return {"sent": sent, "failed": failed}


# ---------- Арын thread ----------
_stop_event = threading.Event()
_thread = None


def reminders_enabled() -> bool:
    return os.getenv("REMINDERS_ENABLED", "1").strip() not in ("0", "false", "no", "")


def _loop() -> None:
    while not _stop_event.is_set():
        try:
            result = send_due_reminders()
            if result.get("sent") or result.get("failed"):
                print("reminders:", result)
        except Exception as error:  # нэг алдаа thread-ийг зогсоохгүй
            print("reminders error:", error)
        _stop_event.wait(REMINDER_CHECK_MINUTES * 60)


def start_background_reminders() -> bool:
    global _thread
    if not reminders_enabled() or (_thread is not None and _thread.is_alive()):
        return False

    _stop_event.clear()
    _thread = threading.Thread(target=_loop, name="deadline-reminders", daemon=True)
    _thread.start()
    return True


def stop_background_reminders() -> None:
    _stop_event.set()


def main() -> int:
    from dotenv import load_dotenv

    from backend.auth import PROJECT_ENV_FILE
    from backend.database import init_database

    load_dotenv(PROJECT_ENV_FILE)
    init_database()
    result = send_due_reminders(force=True)
    print(f"reminders: sent {result['sent']}, failed {result['failed']} (EMAIL_MODE={mailer.get_email_mode()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
