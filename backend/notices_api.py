"""Сургуулийн мэдэгдлийн API.

GET  /api/notices          хадгалсан мэдэгдлүүд (шинэ нь эхэнд)
POST /api/notices/refresh  сургуулийн сайтаас шинээр татах

Сургуулийн сайтыг ачааллахгүйн тулд шинэчлэлийг REFRESH_COOLDOWN_SECONDS
секундэд нэг удаа л зөвшөөрнө. Хэн ч дарсан ижил хязгаар үйлчилнэ.
"""

from fastapi import APIRouter, Depends, Query

from backend import notices
from backend.auth import get_current_user

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
