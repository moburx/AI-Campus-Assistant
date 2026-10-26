"""Gemini-ийн үнэгүй хязгаарыг зохицуулах: model солих fallback.

Үнэгүй хувилбарт хязгаар нь MODEL бүрт тусдаа (жишээ нь өдөрт 20 хүсэлт).
Нэг model "429 RESOURCE_EXHAUSTED" буцаавал жагсаалтын дараагийн model-ийг
оролдоно. Хязгаар нь дууссан model-ийг хэсэг хугацаанд алгасна, ингэснээр
хүсэлт бүрт дэмий 429 авахгүй.

.env:
    GEMINI_MODELS=gemini-3.5-flash,gemini-3.1-flash-lite   # дарааллаар
    GEMINI_MODEL=gemini-3.5-flash                          # хуучин тохиргоо (нэг model)
"""

import os
import re
import threading
import time

DEFAULT_MODEL = "gemini-2.5-flash"
QUOTA_MARKERS = ("429", "RESOURCE_EXHAUSTED")
# Gemini хэзээ дахин оролдохыг хэлээгүй бол энэ хугацаанд алгасна.
DEFAULT_COOLDOWN_SECONDS = 60 * 60
MAX_COOLDOWN_SECONDS = 24 * 60 * 60

_exhausted_until: dict = {}
_lock = threading.Lock()


class QuotaExceededError(Exception):
    """Бүх Gemini model-ийн хязгаар дууссан."""


def configured_models() -> list:
    raw = os.getenv("GEMINI_MODELS") or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
    models = []
    for name in raw.split(","):
        name = name.strip()
        if name and name not in models:
            models.append(name)
    return models or [DEFAULT_MODEL]


def is_quota_error(error: Exception) -> bool:
    text = str(error)
    return any(marker in text for marker in QUOTA_MARKERS)


def retry_after_seconds(error: Exception) -> float:
    """Алдааны мессеж доторх "retryDelay: '6857s'" эсвэл "retry in 1h54m17s"-ийг уншина."""
    text = str(error)

    match = re.search(r"retryDelay['\"]?:\s*['\"](\d+(?:\.\d+)?)s", text)
    if match:
        return min(float(match.group(1)), MAX_COOLDOWN_SECONDS)

    match = re.search(r"retry in (?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", text)
    if match and any(match.groups()):
        hours, minutes, seconds = (float(value or 0) for value in match.groups())
        return min(hours * 3600 + minutes * 60 + seconds, MAX_COOLDOWN_SECONDS)

    return DEFAULT_COOLDOWN_SECONDS


def mark_exhausted(model: str, seconds: float, now: float = None) -> None:
    now = time.monotonic() if now is None else now
    with _lock:
        _exhausted_until[model] = now + seconds


def available_models(now: float = None) -> list:
    now = time.monotonic() if now is None else now
    with _lock:
        return [
            model for model in configured_models()
            if _exhausted_until.get(model, 0) <= now
        ]


def reset_exhausted() -> None:
    """Тест болон гараар дахин эхлүүлэхэд."""
    with _lock:
        _exhausted_until.clear()


def call_with_model_fallback(call, models: list = None):
    """call(model)-ийг model бүрээр оролдоно. Хязгаарын алдаанаас бусдыг шууд дамжуулна."""
    candidates = models if models is not None else available_models()
    if not candidates:
        raise QuotaExceededError("All Gemini models have reached their free quota")

    last_error = None
    for model in candidates:
        try:
            return call(model)
        except Exception as error:
            if not is_quota_error(error):
                raise
            print(f"gemini quota reached for {model}, trying next model")
            mark_exhausted(model, retry_after_seconds(error))
            last_error = error

    raise QuotaExceededError("All Gemini models have reached their free quota") from last_error
