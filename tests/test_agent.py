"""AI агентын тест.

Жинхэнэ AI руу хүсэлт явуулахгүй. Оронд нь урьдчилан бичсэн "хуурамч"
хариу буцаадаг client ашиглаж, агентын давталт (loop) болон хэрэгслүүд
зөв ажиллаж байгааг шалгана.
"""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from backend import agent, assistant
from backend.agent import TOOL_DEFINITIONS, ToolExecutor


def days_from_today(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def user_id_of(client, headers) -> int:
    return client.get("/api/auth/me", headers=headers).json()["id"]


# ---------- Хэрэгслийн тодорхойлолт ----------
def test_every_tool_has_a_handler():
    executor = ToolExecutor(user_id=1)
    for tool in TOOL_DEFINITIONS:
        assert callable(getattr(executor, f"tool_{tool['name']}", None)), tool["name"]
        assert tool["parameters"]["type"] == "object"


def test_no_delete_tool_is_exposed():
    names = {tool["name"] for tool in TOOL_DEFINITIONS}
    assert not any("delete" in name for name in names)


# ---------- ToolExecutor ----------
def test_add_assignment_tool(client, user_headers):
    executor = ToolExecutor(user_id_of(client, user_headers))

    result = executor.run("add_assignment", {
        "title": "Lab report",
        "course": "Physics",
        "deadline": days_from_today(3),
        "priority": "high",
    })

    assert result["ok"] is True
    assert result["assignment"]["title"] == "Lab report"
    assert executor.actions[0]["tool"] == "add_assignment"
    assert executor.actions[0]["ok"] is True

    saved = client.get("/api/assignments", headers=user_headers).json()
    assert saved[0]["title"] == "Lab report"
    assert saved[0]["priority"] == "high"


def test_add_assignment_tool_rejects_bad_date(client, user_headers):
    executor = ToolExecutor(user_id_of(client, user_headers))

    result = executor.run("add_assignment", {
        "title": "Lab", "course": "Physics", "deadline": "next friday",
    })

    assert result["ok"] is False
    assert "deadline" in result["error"]
    assert executor.actions[0]["ok"] is False
    assert client.get("/api/assignments", headers=user_headers).json() == []


def test_add_assignment_tool_requires_fields(client, user_headers):
    executor = ToolExecutor(user_id_of(client, user_headers))
    result = executor.run("add_assignment", {"title": "Only title"})
    assert result["ok"] is False


def test_update_tool_marks_completed(client, user_headers, create_assignment):
    item = create_assignment(user_headers)
    executor = ToolExecutor(user_id_of(client, user_headers))

    result = executor.run("update_assignment", {"assignment_id": item["id"], "completed": True})

    assert result["ok"] is True
    assert result["assignment"]["completed"] is True
    assert executor.actions[0]["changed"] == ["completed"]


def test_update_tool_ignores_unknown_and_null_fields(client, user_headers, create_assignment):
    item = create_assignment(user_headers)
    executor = ToolExecutor(user_id_of(client, user_headers))

    result = executor.run("update_assignment", {
        "assignment_id": str(item["id"]),
        "title": "New title",
        "notes": None,
        "user_id": 999,
    })

    assert result["ok"] is True
    assert result["assignment"]["title"] == "New title"
    assert result["changed"] == ["title"]


def test_update_tool_cannot_touch_other_users(client, make_user, create_assignment):
    alice = make_user("alice")
    bob = make_user("bob")
    item = create_assignment(alice)

    executor = ToolExecutor(user_id_of(client, bob))
    result = executor.run("update_assignment", {"assignment_id": item["id"], "completed": True})

    assert result == {"ok": False, "error": "Assignment not found."}
    assert client.get("/api/assignments", headers=alice).json()[0]["completed"] is False


def test_update_tool_without_id(client, user_headers):
    executor = ToolExecutor(user_id_of(client, user_headers))
    result = executor.run("update_assignment", {"completed": True})
    assert result["ok"] is False


def test_unknown_tool(client, user_headers):
    executor = ToolExecutor(user_id_of(client, user_headers))
    assert executor.run("delete_everything", {}) == {"ok": False, "error": "Unknown tool: delete_everything"}
    assert executor.actions == []


def test_list_tool_filters_and_sorts(client, user_headers, create_assignment):
    create_assignment(user_headers, title="Later", course="Math", deadline=days_from_today(10))
    create_assignment(user_headers, title="Sooner", course="Math", deadline=days_from_today(1))
    done = create_assignment(user_headers, title="Done", course="Art", deadline=days_from_today(0))
    client.patch(f"/api/assignments/{done['id']}", json={"completed": True}, headers=user_headers)

    executor = ToolExecutor(user_id_of(client, user_headers))

    everything = executor.run("list_assignments", {})
    assert [item["title"] for item in everything["assignments"]] == ["Sooner", "Later", "Done"]

    open_math = executor.run("list_assignments", {"status": "incomplete", "course": "mat"})
    assert open_math["count"] == 2

    bad = executor.run("list_assignments", {"status": "weird"})
    assert bad["ok"] is False


def test_statistics_and_courses_tools(client, user_headers, create_assignment):
    create_assignment(user_headers, course="Math", deadline=days_from_today(-2))
    create_assignment(user_headers, course="Math", deadline=days_from_today(2))
    executor = ToolExecutor(user_id_of(client, user_headers))

    stats = executor.run("get_statistics", {})
    assert stats["total"] == 2
    assert stats["overdue"] == 1
    assert stats["due_within_7_days"] == 1

    courses = executor.run("list_courses", {})
    assert courses["courses"] == [{"name": "Math", "total": 2, "completed": 0}]


# ---------- Claude агентын давталт (хуурамч client) ----------
class FakeClaudeClient:
    """messages.create дуудлага бүрд дараалсан хариуг буцаана."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


def claude_text(text):
    return SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=text)],
    )


def claude_tool_use(name, tool_input, tool_id="toolu_1"):
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input)],
    )


def test_claude_agent_runs_tool_then_answers(client, user_headers):
    executor = ToolExecutor(user_id_of(client, user_headers))
    fake = FakeClaudeClient([
        claude_tool_use("add_assignment", {
            "title": "Essay", "course": "Writing", "deadline": days_from_today(5),
        }),
        claude_text("Added Essay."),
    ])

    answer = agent.run_claude_agent("add essay", executor, client=fake, model="test")

    assert answer == "Added Essay."
    assert len(fake.requests) == 2
    tool_result = fake.requests[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "toolu_1"
    assert '"ok": true' in tool_result["content"]
    assert client.get("/api/assignments", headers=user_headers).json()[0]["title"] == "Essay"


def test_claude_agent_stops_after_max_steps(client, user_headers):
    executor = ToolExecutor(user_id_of(client, user_headers))
    responses = [claude_tool_use("list_assignments", {}) for _ in range(agent.MAX_TOOL_STEPS)]
    responses.append(claude_text("Final"))
    fake = FakeClaudeClient(responses)

    answer = agent.run_claude_agent("loop", executor, client=fake, model="test")

    assert answer == "Final"
    assert executor.calls == agent.MAX_TOOL_STEPS
    assert fake.requests[-1]["tool_choice"] == {"type": "none"}


def test_claude_agent_cut_off_raises(client, user_headers):
    executor = ToolExecutor(user_id_of(client, user_headers))
    cut = SimpleNamespace(stop_reason="max_tokens", content=[SimpleNamespace(type="text", text="Hal")])

    with pytest.raises(RuntimeError):
        agent.run_claude_agent("x", executor, client=FakeClaudeClient([cut]), model="test")


# ---------- Gemini агентын давталт (хуурамч client) ----------
class FakeGeminiClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.models = SimpleNamespace(generate_content=self.generate_content)

    def generate_content(self, **kwargs):
        # contents жагсаалт цааш өөрчлөгдөх тул хуулбарыг хадгална.
        self.requests.append({**kwargs, "contents": list(kwargs["contents"])})
        return self.responses.pop(0)


def test_gemini_agent_runs_tool_then_answers(client, user_headers, create_assignment):
    types = pytest.importorskip("google.genai.types")

    item = create_assignment(user_headers, title="Quiz")
    executor = ToolExecutor(user_id_of(client, user_headers))

    call_response = types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
            id="call-1",
            name="update_assignment",
            args={"assignment_id": item["id"], "completed": True},
        ))]),
        finish_reason="STOP",
    )])
    text_response = types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part(text="Marked Quiz as done.")]),
        finish_reason="STOP",
    )])
    fake = FakeGeminiClient([call_response, text_response])

    answer = agent.run_gemini_agent("done with quiz", executor, client=fake, model="test")

    assert answer == "Marked Quiz as done."
    second_contents = fake.requests[1]["contents"]
    assert second_contents[1].role == "model"
    function_response = second_contents[2].parts[0].function_response
    assert function_response.name == "update_assignment"
    assert function_response.id == "call-1"
    assert function_response.response["ok"] is True
    assert client.get("/api/assignments", headers=user_headers).json()[0]["completed"] is True


def test_gemini_agent_declares_all_tools(client, user_headers):
    types = pytest.importorskip("google.genai.types")

    executor = ToolExecutor(user_id_of(client, user_headers))
    text_response = types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part(text="Hi")]),
        finish_reason="STOP",
    )])
    fake = FakeGeminiClient([text_response])

    agent.run_gemini_agent("hello", executor, client=fake, model="test")

    config = fake.requests[0]["config"]
    declared = {fd.name for fd in config.tools[0].function_declarations}
    assert declared == {tool["name"] for tool in TOOL_DEFINITIONS}
    assert config.automatic_function_calling.disable is True


# ---------- Endpoint ба агент ----------
def test_endpoint_returns_agent_actions(client, make_user, monkeypatch):
    headers = make_user("jisoo", language="ko")

    def fake_agent(message, executor):
        executor.run("add_assignment", {
            "title": "보고서", "course": "사물인터넷", "deadline": days_from_today(9),
        })
        return "보고서를 추가했어요."

    monkeypatch.setattr(assistant, "get_providers", lambda: [("gemini", fake_agent, None)])

    data = client.post(
        "/api/assistant",
        json={"question": "다음 주 월요일까지 IoT 보고서 추가해줘"},
        headers=headers,
    ).json()

    assert data["mode"] == "agent"
    assert data["answer"] == "보고서를 추가했어요."
    assert data["actions"][0]["tool"] == "add_assignment"
    assert data["actions"][0]["title"] == "보고서"
    assert len(client.get("/api/assignments", headers=headers).json()) == 1


def test_endpoint_reports_actions_when_agent_crashes_after_change(client, make_user, monkeypatch):
    headers = make_user("jisoo", language="ko")
    advice_calls = []

    def crashing_agent(message, executor):
        executor.run("add_assignment", {
            "title": "보고서", "course": "IoT", "deadline": days_from_today(1),
        })
        raise RuntimeError("network down")

    def advice(message):
        advice_calls.append(message)
        return "advice"

    monkeypatch.setattr(assistant, "get_providers", lambda: [("gemini", crashing_agent, advice)])

    data = client.post("/api/assistant", json={}, headers=headers).json()

    assert data["mode"] == "agent"
    assert data["answer"] == "과제를 추가했습니다: 보고서"
    # Давхар нэмэхгүйн тулд дахин оролдохгүй.
    assert advice_calls == []
    assert len(client.get("/api/assignments", headers=headers).json()) == 1


def test_describe_actions_in_each_language():
    actions = [
        {"tool": "add_assignment", "ok": True, "title": "A", "completed": False, "changed": ["created"]},
        {"tool": "update_assignment", "ok": True, "title": "B", "completed": True, "changed": ["completed"]},
        {"tool": "update_assignment", "ok": True, "title": "C", "completed": False, "changed": ["deadline"]},
        {"tool": "add_assignment", "ok": False, "error": "bad date"},
    ]

    for code in assistant.RULE_TEXT:
        lines = assistant.describe_actions(actions, code).splitlines()
        assert len(lines) == 4
        assert "A" in lines[0] and "B" in lines[1] and "C" in lines[2]
        assert "bad date" in lines[3]
def test_call_with_retry_retries_temporary_errors(monkeypatch):
    monkeypatch.setattr(agent.time, "sleep", lambda seconds: None)
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("503 UNAVAILABLE")
        return "ok"

    assert agent.call_with_retry(flaky) == "ok"
    assert len(attempts) == 3


def test_call_with_retry_does_not_retry_other_errors(monkeypatch):
    monkeypatch.setattr(agent.time, "sleep", lambda seconds: None)
    attempts = []

    def broken():
        attempts.append(1)
        raise ValueError("bad request")

    with pytest.raises(ValueError):
        agent.call_with_retry(broken)
    assert len(attempts) == 1