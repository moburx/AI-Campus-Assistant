"""Gemini-ийн үнэгүй хязгаар (429) дууссан үеийн model fallback ба мэдэгдэл."""

from types import SimpleNamespace

import pytest

from backend import agent, assistant, gemini_models, notice_summary
from backend.agent import ToolExecutor
from backend.gemini_models import QuotaExceededError

# Gemini-ийн жинхэнэ алдааны мессежийн товчилсон хэлбэр
QUOTA_MESSAGE = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota. "
    "Please retry in 1h54m17.84s.', 'status': 'RESOURCE_EXHAUSTED', 'details': "
    "[{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '6857s'}]}}"
)


class QuotaError(Exception):
    pass


# ---------- Тохиргоо ----------
def test_models_come_from_gemini_models_in_order(monkeypatch):
    monkeypatch.setenv("GEMINI_MODELS", " model-a , model-b,model-a,, ")
    assert gemini_models.configured_models() == ["model-a", "model-b"]


def test_single_gemini_model_still_works(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "model-a")
    assert gemini_models.configured_models() == ["model-a"]


def test_default_model_when_nothing_is_set():
    assert gemini_models.configured_models() == [gemini_models.DEFAULT_MODEL]


@pytest.mark.parametrize(
    "message, seconds",
    [
        (QUOTA_MESSAGE, 6857),
        ("429 RESOURCE_EXHAUSTED Please retry in 1h2m3s.", 3723),
        ("429 RESOURCE_EXHAUSTED Please retry in 45s.", 45),
        ("429 RESOURCE_EXHAUSTED", gemini_models.DEFAULT_COOLDOWN_SECONDS),
    ],
)
def test_retry_after_is_read_from_the_error(message, seconds):
    assert gemini_models.retry_after_seconds(QuotaError(message)) == pytest.approx(seconds)


# ---------- Fallback ----------
def test_quota_error_switches_to_next_model(monkeypatch):
    monkeypatch.setenv("GEMINI_MODELS", "model-a,model-b")
    tried = []

    def call(model):
        tried.append(model)
        if model == "model-a":
            raise QuotaError(QUOTA_MESSAGE)
        return f"answer from {model}"

    assert gemini_models.call_with_model_fallback(call) == "answer from model-b"
    assert tried == ["model-a", "model-b"]

    # Хязгаар дууссан model-ийг дараагийн удаа дэмий оролдохгүй.
    tried.clear()
    assert gemini_models.call_with_model_fallback(call) == "answer from model-b"
    assert tried == ["model-b"]


def test_exhausted_model_comes_back_after_cooldown(monkeypatch):
    monkeypatch.setenv("GEMINI_MODELS", "model-a,model-b")
    gemini_models.mark_exhausted("model-a", 60, now=1000)

    assert gemini_models.available_models(now=1030) == ["model-b"]
    assert gemini_models.available_models(now=1061) == ["model-a", "model-b"]


def test_all_models_exhausted_raises_quota_error(monkeypatch):
    monkeypatch.setenv("GEMINI_MODELS", "model-a,model-b")

    def call(model):
        raise QuotaError(QUOTA_MESSAGE)

    with pytest.raises(QuotaExceededError):
        gemini_models.call_with_model_fallback(call)

    # Хоёулаа алгасагдах тул дахин дуудахад шууд алдаа (API руу хүсэлт явахгүй).
    with pytest.raises(QuotaExceededError):
        gemini_models.call_with_model_fallback(lambda model: pytest.fail("should not be called"))


def test_other_errors_do_not_try_next_model(monkeypatch):
    monkeypatch.setenv("GEMINI_MODELS", "model-a,model-b")
    tried = []

    def call(model):
        tried.append(model)
        raise ValueError("400 INVALID_ARGUMENT")

    with pytest.raises(ValueError):
        gemini_models.call_with_model_fallback(call)
    assert tried == ["model-a"]
    assert gemini_models.available_models() == ["model-a", "model-b"]


def test_quota_errors_are_not_retried_with_sleep(monkeypatch):
    monkeypatch.setattr(agent.time, "sleep", lambda seconds: pytest.fail("should not sleep"))
    attempts = []

    def limited():
        attempts.append(1)
        raise QuotaError(QUOTA_MESSAGE)

    with pytest.raises(QuotaError):
        agent.call_with_retry(limited)
    assert len(attempts) == 1


# ---------- Агент ----------
def test_gemini_agent_uses_next_model_when_quota_is_reached(client, user_headers, monkeypatch):
    types = pytest.importorskip("google.genai.types")
    monkeypatch.setenv("GEMINI_MODELS", "model-a,model-b")
    used = []

    def generate_content(model, contents, config):
        used.append(model)
        if model == "model-a":
            raise QuotaError(QUOTA_MESSAGE)
        return types.GenerateContentResponse(candidates=[types.Candidate(
            content=types.Content(role="model", parts=[types.Part(text="Hi from B")]),
            finish_reason="STOP",
        )])

    fake = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    user_id = client.get("/api/auth/me", headers=user_headers).json()["id"]

    answer = agent.run_gemini_agent("hello", ToolExecutor(user_id), client=fake)

    assert answer == "Hi from B"
    assert used == ["model-a", "model-b"]


# ---------- Endpoint: хэрэглэгчид мэдэгдэх ----------
def test_assistant_reports_ai_quota_and_skips_plain_advice(client, user_headers, create_assignment, monkeypatch):
    create_assignment(user_headers, title="Report")

    def agent_out_of_quota(message, executor):
        raise QuotaExceededError("All Gemini models have reached their free quota")

    def advice(message):
        pytest.fail("plain advice should not be called when the quota is reached")

    monkeypatch.setattr(assistant, "get_providers", lambda: [("gemini", agent_out_of_quota, advice)])

    data = client.post("/api/assistant", json={"question": "plan?"}, headers=user_headers).json()

    assert data["source"] == "rules"
    assert data["notice"] == "ai_quota"
    assert "Report" in data["answer"]


def test_assistant_has_no_notice_for_other_errors(client, user_headers, monkeypatch):
    def broken(*args):
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(assistant, "get_providers", lambda: [("gemini", broken, broken)])

    data = client.post("/api/assistant", json={"question": "plan?"}, headers=user_headers).json()

    assert data["source"] == "rules"
    assert data["notice"] is None


# ---------- Мэдэгдлийн AI тайлбар ----------
def test_notice_summary_reports_daily_limit(client, user_headers, monkeypatch):
    def out_of_quota(notice_id, language):
        raise notice_summary.AIQuotaError("quota")

    monkeypatch.setattr(notice_summary, "get_or_create_summary", out_of_quota)

    response = client.post("/api/notices/1/summary", headers=user_headers)

    assert response.status_code == 503
    assert response.json()["detail"] == "AI daily limit reached."


def test_summarize_with_gemini_raises_quota_error(monkeypatch):
    pytest.importorskip("google.genai.types")
    monkeypatch.setenv("GEMINI_MODELS", "model-a,model-b")

    def generate_content(**kwargs):
        raise QuotaError(QUOTA_MESSAGE)

    fake = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    detail = {"title": "T", "body": "B", "attachments": [], "images": [], "image_data": []}
    notice = {"title": "T", "posted_at": "2026-10-12", "source": "국제교류원 Notice"}

    with pytest.raises(notice_summary.AIQuotaError):
        notice_summary.summarize_with_gemini(notice, detail, "mn", client=fake)
