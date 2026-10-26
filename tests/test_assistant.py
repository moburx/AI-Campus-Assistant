"""AI туслахын тест.

Жинхэнэ AI үйлчилгээ рүү хүсэлт явуулахгүйн тулд дуудлагуудыг
monkeypatch-аар орлуулна.
"""

from datetime import date, timedelta

from backend import assistant
from backend.assistant import rule_based_advice


def days_from_today(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


# ---------- Дүрмийн зөвлөмж ----------
def test_rule_advice_empty_in_each_language():
    for code, text in assistant.RULE_TEXT.items():
        assert rule_based_advice([], code) == text["empty"]


def test_rule_advice_unknown_language_falls_back_to_english():
    assert rule_based_advice([], "xx") == assistant.RULE_TEXT["en"]["empty"]


def test_rule_advice_orders_by_deadline_and_marks_overdue():
    today = date(2026, 10, 17)
    tasks = [
        {"title": "Later", "course": "A", "deadline": "2026-10-26", "priority": "medium"},
        {"title": "Old", "course": "B", "deadline": "2026-10-10", "priority": "medium"},
        {"title": "Soon", "course": "C", "deadline": "2026-10-19", "priority": "medium"},
    ]

    lines = rule_based_advice(tasks, "en", today=today).splitlines()

    assert lines[1] == "1. Old (B): overdue by 7 day(s)!"
    assert lines[2] == "2. Soon (C): 2 day(s) left"
    assert lines[3] == "3. Later (A): 9 day(s) left"


def test_rule_advice_high_priority_first_on_same_day():
    today = date(2026, 10, 17)
    tasks = [
        {"title": "Normal", "course": "A", "deadline": "2026-10-20", "priority": "low"},
        {"title": "Urgent", "course": "B", "deadline": "2026-10-20", "priority": "high"},
    ]

    lines = rule_based_advice(tasks, "ko", today=today).splitlines()

    assert lines[1].startswith("1. Urgent")
    assert "[중요]" in lines[1]


def test_rule_advice_due_today_and_limit_five():
    today = date(2026, 10, 17)
    tasks = [
        {"title": f"T{i}", "course": "C", "deadline": "2026-10-17", "priority": "medium"}
        for i in range(8)
    ]

    lines = rule_based_advice(tasks, "en", today=today).splitlines()

    # header + 5 даалгавар + footer
    assert len(lines) == 7
    assert "due today" in lines[1]


# ---------- Endpoint ----------
def test_assistant_requires_token(client):
    assert client.post("/api/assistant", json={}).status_code in (401, 403)


def test_assistant_without_keys_uses_rules(client, make_user, create_assignment):
    headers = make_user("minji", language="ko")
    create_assignment(headers, title="Report", deadline=days_from_today(2))

    data = client.post("/api/assistant", json={}, headers=headers).json()

    assert data["source"] == "rules"
    assert data["assignment_count"] == 1
    assert data["answer"].startswith("마감일 순 계획:")


def test_assistant_ignores_completed_assignments(client, user_headers, create_assignment):
    done = create_assignment(user_headers)
    client.patch(
        f"/api/assignments/{done['id']}",
        json={"completed": True},
        headers=user_headers,
    )

    data = client.post("/api/assistant", json={}, headers=user_headers).json()

    assert data["assignment_count"] == 0
    assert data["answer"] == assistant.RULE_TEXT["en"]["empty"]


def failing(*args):
    raise RuntimeError("quota exceeded")


def test_assistant_uses_agent_when_available(client, user_headers, create_assignment, monkeypatch):
    create_assignment(user_headers, title="Essay")
    sent = {}

    def fake_agent(message, executor):
        sent["message"] = message
        return "Start with Essay."

    monkeypatch.setattr(
        assistant,
        "get_providers",
        lambda: [("gemini", fake_agent, failing)],
    )

    data = client.post(
        "/api/assistant",
        json={"question": "What first?"},
        headers=user_headers,
    ).json()

    assert data == {
        "answer": "Start with Essay.",
        "source": "gemini",
        "mode": "agent",
        "actions": [],
        "assignment_count": 1,
        "notice": None,
    }
    assert '"title": "Essay"' in sent["message"]
    assert "reply_language: en" in sent["message"]
    assert "Student message: What first?" in sent["message"]


def test_assistant_uses_plain_advice_when_agent_fails(client, user_headers, create_assignment, monkeypatch):
    create_assignment(user_headers)

    monkeypatch.setattr(
        assistant,
        "get_providers",
        lambda: [("gemini", failing, lambda message: "Plain advice")],
    )

    data = client.post("/api/assistant", json={}, headers=user_headers).json()

    assert data["source"] == "gemini"
    assert data["mode"] == "advice"
    assert data["answer"] == "Plain advice"


def test_assistant_falls_back_when_provider_fails(client, user_headers, create_assignment, monkeypatch):
    create_assignment(user_headers)

    monkeypatch.setattr(
        assistant,
        "get_providers",
        lambda: [
            ("gemini", failing, failing),
            ("claude", lambda message, executor: "Claude answer", failing),
        ],
    )

    data = client.post("/api/assistant", json={}, headers=user_headers).json()

    assert data["source"] == "claude"
    assert data["answer"] == "Claude answer"


def test_assistant_falls_back_to_rules_on_empty_answers(client, user_headers, monkeypatch):
    monkeypatch.setattr(
        assistant,
        "get_providers",
        lambda: [("gemini", lambda message, executor: "   ", lambda message: "")],
    )

    data = client.post("/api/assistant", json={}, headers=user_headers).json()
    assert data["source"] == "rules"
    assert data["mode"] == "rules"


def test_assistant_only_sends_own_assignments(client, make_user, create_assignment, monkeypatch):
    alice = make_user("alice")
    bob = make_user("bob")
    create_assignment(alice, title="Alice secret")
    create_assignment(bob, title="Bob task")
    sent = {}

    def fake(message, executor):
        sent["message"] = message
        sent["listed"] = executor.run("list_assignments", {})
        return "ok"

    monkeypatch.setattr(assistant, "get_providers", lambda: [("gemini", fake, failing)])
    client.post("/api/assistant", json={}, headers=bob)

    assert "Bob task" in sent["message"]
    assert "Alice secret" not in sent["message"]
    assert [item["title"] for item in sent["listed"]["assignments"]] == ["Bob task"]


def test_assistant_question_too_long_returns_422(client, user_headers):
    response = client.post(
        "/api/assistant",
        json={"question": "x" * 501},
        headers=user_headers,
    )
    assert response.status_code == 422


def test_get_providers_reads_environment(monkeypatch):
    assert assistant.get_providers() == []

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")

    names = [provider[0] for provider in assistant.get_providers()]
    assert names == ["gemini", "claude"]
