"""/api/notices endpoint-уудын тест (сургуулийн сайт руу хүсэлт илгээхгүй)."""

from datetime import timedelta

from backend import notices, notices_api


def fake_board(board_id):
    return [{
        "board_id": board_id,
        "ntt_id": f"{board_id}-1",
        "title": f"Notice from {board_id}",
        "writer": "국제교류원",
        "posted_at": "2026-10-20",
        "pinned": False,
        "is_new": True,
        "url": notices.notice_url(board_id, f"{board_id}-1"),
    }]


def test_notices_require_login(client):
    assert client.get("/api/notices").status_code in (401, 403)
    assert client.post("/api/notices/refresh").status_code in (401, 403)


def test_notices_empty_at_first(client, user_headers):
    data = client.get("/api/notices", headers=user_headers).json()
    assert data == {"notices": [], "last_refreshed": None}


def test_refresh_then_list(client, user_headers, monkeypatch):
    monkeypatch.setattr(notices, "fetch_recent", fake_board)

    result = client.post("/api/notices/refresh", headers=user_headers).json()

    assert result["refreshed"] is True
    assert result["new"] == len(notices.SOURCES)
    assert result["errors"] == []
    assert result["last_refreshed"]

    data = client.get("/api/notices", headers=user_headers).json()
    assert len(data["notices"]) == len(notices.SOURCES)
    assert data["notices"][0]["url"].startswith("https://www.hanbat.ac.kr/bbs/")
    assert data["notices"][0]["source"]


def test_refresh_cooldown(client, user_headers, monkeypatch):
    calls = []

    def counting_fetch(board_id):
        calls.append(board_id)
        return []

    monkeypatch.setattr(notices, "fetch_recent", counting_fetch)

    first = client.post("/api/notices/refresh", headers=user_headers).json()
    second = client.post("/api/notices/refresh", headers=user_headers).json()

    assert first["refreshed"] is True
    assert second["refreshed"] is False
    assert 0 < second["retry_after"] <= notices_api.REFRESH_COOLDOWN_SECONDS
    assert len(calls) == len(notices.SOURCES)


def test_refresh_allowed_after_cooldown(client, user_headers, monkeypatch):
    monkeypatch.setattr(notices, "fetch_recent", lambda board_id: [])

    notices.set_last_refreshed(
        notices.utc_now() - timedelta(seconds=notices_api.REFRESH_COOLDOWN_SECONDS + 1)
    )

    result = client.post("/api/notices/refresh", headers=user_headers).json()
    assert result["refreshed"] is True


def test_notices_limit_validation(client, user_headers):
    assert client.get("/api/notices?limit=0", headers=user_headers).status_code == 422
    assert client.get("/api/notices?limit=201", headers=user_headers).status_code == 422


def test_notices_scope_filter(client, user_headers):
    from backend.database import get_connection

    with get_connection() as connection:
        notices.save_notices(connection, [
            {"board_id": "BBSMSTR_000000000050", "ntt_id": "A", "title": "장학금", "writer": "", "posted_at": "2026-10-20",
             "pinned": False, "url": "u1", "international": True},
            {"board_id": "BBSMSTR_000000000050", "ntt_id": "B", "title": "수강신청", "writer": "", "posted_at": "2026-10-21",
             "pinned": False, "url": "u2", "international": False},
        ])

    all_items = client.get("/api/notices", headers=user_headers).json()["notices"]
    international = client.get("/api/notices?scope=international", headers=user_headers).json()["notices"]

    assert len(all_items) == 2
    assert [item["title"] for item in international] == ["장학금"]
    assert client.get("/api/notices?scope=nope", headers=user_headers).status_code == 422


def test_notices_academic_scope(client, user_headers):
    from backend.database import get_connection

    with get_connection() as connection:
        notices.save_notices(connection, [
            {"board_id": "BBSMSTR_000000000042", "ntt_id": "C", "title": "계절학기", "writer": "", "posted_at": "2026-10-22",
             "pinned": False, "url": "u3", "international": False},
            {"board_id": "BBSMSTR_000000000050", "ntt_id": "D", "title": "공지", "writer": "", "posted_at": "2026-10-23",
             "pinned": False, "url": "u4", "international": False},
        ])

    academic = client.get("/api/notices?scope=academic", headers=user_headers).json()["notices"]

    assert [item["title"] for item in academic] == ["계절학기"]
