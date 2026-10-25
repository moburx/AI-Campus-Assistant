"""Сургуулийн мэдэгдлийн API.

GET  /api/notices                хадгалсан мэдэгдлүүд (шинэ нь эхэнд)
POST /api/notices/refresh        сургуулийн сайтаас шинээр татах
POST /api/notices/{id}/summary   мэдэгдлийг хэрэглэгчийн хэлээр AI-аар тайлбарлах

Сургуулийн сайтыг ачааллахгүйн тулд шинэчлэлийг REFRESH_COOLDOWN_SECONDS
секундэд нэг удаа л зөвшөөрнө. Хэн ч дарсан ижил хязгаар үйлчилнэ.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend import notice_summary, notices
from backend.auth import LanguageCode, get_current_user

router = APIRouter(prefix="/api/notices", tags=["notices"])

REFRESH_COOLDOWN_SECONDS = 10 * 60


@router.get("")
def get_notices(
    limit: int = Query(default=30, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    return {
        "notices": notices.list_saved_notices(limit),
        "last_refreshed": notices.get_last_refreshed(),
    }


@router.post("/refresh")
def refresh(current_user: dict = Depends(get_current_user)):
    elapsed = notices.seconds_since_last_refresh()

    if elapsed is not None and elapsed < REFRESH_COOLDOWN_SECONDS:
        return {
            "refreshed": False,
            "retry_after": int(REFRESH_COOLDOWN_SECONDS - elapsed),
            "last_refreshed": notices.get_last_refreshed(),
        }

    result = notices.refresh_notices()
    return {
        "refreshed": True,
        **result,
        "last_refreshed": notices.get_last_refreshed(),
    }


@router.post("/{notice_id}/summary")
def summarize_notice(
    notice_id: int,
    language: Optional[LanguageCode] = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    """Хэл заагаагүй бол хэрэглэгчийн профайлын хэлийг ашиглана."""
    language = language or current_user["preferred_language"]

    try:
        return notice_summary.get_or_create_summary(notice_id, language)
    except notice_summary.NotFoundError:
        raise HTTPException(status_code=404, detail="Notice not found.")
    except notice_summary.AIUnavailableError:
        raise HTTPException(status_code=503, detail="AI summary is not available right now.")
    except Exception as error:
        print("notice summary error:", error)
        raise HTTPException(status_code=502, detail="Could not summarize this notice.")
