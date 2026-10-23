"""공지사항 수집기 테스트.

Сургуулийн сайт руу хүсэлт илгээхгүйн тулд tests/fixtures/ дотор
хадгалсан HTML-ээр шалгана.
"""

from pathlib import Path

import httpx

from backend import notices
from backend.notices import is_relevant, parse_notice_list

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_international_notice_board():
    items = parse_notice_list(load("hanbat_087_notice.html"), "BBSMSTR_000000000087")

    assert len(items) >= 10
    titles = [item["title"] for item in items]
    assert "제33회 토익경시대회 모집(장학금10~30만원)" in titles

    toeic = next(item for item in items if item["title"].startswith("제33회 토익경시대회"))
    assert toeic["ntt_id"] == "B000000171040Nt4iC3a"
    assert toeic["posted_at"] == "2026-10-12"
    assert toeic["writer"] == "국제교류원"
    assert toeic["url"] == (
        "https://www.hanbat.ac.kr/bbs/BBSMSTR_000000000087/view.do?nttId=B000000171040Nt4iC3a"
    )


def test_every_item_has_required_fields():
    for name, board in [
        ("hanbat_087_notice.html", "BBSMSTR_000000000087"),
        ("hanbat_090_announcement.html", "BBSMSTR_000000000090"),
        ("hanbat_050_general.html", "BBSMSTR_000000000050"),
    ]:
        items = parse_notice_list(load(name), board)
        assert items, name
        for item in items:
            assert item["ntt_id"].startswith("B"), item
            assert item["title"], item
            assert len(item["posted_at"]) == 10, item
            assert item["board_id"] == board


def test_pinned_notices_are_not_duplicated():
    items = parse_notice_list(load("hanbat_087_notice.html"), "BBSMSTR_000000000087")
    ids = [item["ntt_id"] for item in items]
    assert len(ids) == len(set(ids))


def test_pinned_and_new_flags():
    items = parse_notice_list(load("hanbat_050_general.html"), "BBSMSTR_000000000050")
    assert any(item["pinned"] for item in items)
    assert any(not item["pinned"] for item in items)

    international = parse_notice_list(load("hanbat_087_notice.html"), "BBSMSTR_000000000087")
    assert any(item["is_new"] for item in international)


def test_empty_or_broken_html_returns_nothing():
    assert parse_notice_list("", "X") == []
    assert parse_notice_list("<html><tbody><tr><td>no link</td></tr></tbody></html>", "X") == []


def test_keyword_filter():
    notice = {"title": "외국인 유학생 장학금 안내"}
    assert is_relevant(notice, []) is True
    assert is_relevant(notice, ["유학생"]) is True
    assert is_relevant(notice, ["International"]) is False
    assert is_relevant({"title": "International Week"}, ["international"]) is True


def test_fetch_board_uses_page_and_filters(monkeypatch):
    html = load("hanbat_050_general.html")
    requested = []

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(200, text=html)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setitem(
        notices.SOURCES,
        "BBSMSTR_000000000050",
        {"name": "test", "keywords": ["천원의 아침밥"]},
    )

    items = notices.fetch_board("BBSMSTR_000000000050", page=2, client=client)

    assert requested == ["https://www.hanbat.ac.kr/bbs/BBSMSTR_000000000050/list.do?pageIndex=2"]
    assert len(items) == 1
    assert "천원의 아침밥" in items[0]["title"]


def test_fetch_board_raises_on_http_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))

    try:
        notices.fetch_board("BBSMSTR_000000000087", client=client)
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("expected HTTPStatusError")


# ---------- DB-д хадгалах ----------
def sample_notice(ntt_id, title="Notice", posted_at="2026-10-20", board_id="BBSMSTR_000000000087", pinned=False):
    return {
        "board_id": board_id,
        "ntt_id": ntt_id,
        "title": title,
        "writer": "국제교류원",
        "posted_at": posted_at,
        "pinned": pinned,
        "is_new": False,
        "url": notices.notice_url(board_id, ntt_id),
    }


def test_save_notices_skips_duplicates(client):
    from backend.database import get_connection

    items = [sample_notice("B1"), sample_notice("B2")]

    with get_connection() as connection:
        assert notices.save_notices(connection, items) == 2
    with get_connection() as connection:
        assert notices.save_notices(connection, items) == 0

    assert len(notices.list_saved_notices()) == 2


def test_save_notices_updates_changed_title(client):
    from backend.database import get_connection

    with get_connection() as connection:
        notices.save_notices(connection, [sample_notice("B1", title="Old")])
    with get_connection() as connection:
        notices.save_notices(connection, [sample_notice("B1", title="New", pinned=True)])

    saved = notices.list_saved_notices()
    assert len(saved) == 1
    assert saved[0]["title"] == "New"
    assert saved[0]["pinned"] is True


def test_list_saved_notices_newest_first(client):
    from backend.database import get_connection

    with get_connection() as connection:
        notices.save_notices(connection, [
            sample_notice("B1", posted_at="2026-10-07"),
            sample_notice("B2", posted_at="2026-10-20"),
            sample_notice("B3", posted_at="2026-10-12"),
        ])

    dates = [item["posted_at"] for item in notices.list_saved_notices()]
    assert dates == ["2026-10-20", "2026-10-12", "2026-10-07"]
    assert notices.list_saved_notices(limit=1)[0]["posted_at"] == "2026-10-20"


def test_refresh_notices_continues_after_board_error(client):
    def fake_fetch(board_id):
        if board_id == "BBSMSTR_000000000090":
            raise RuntimeError("site down")
        return [sample_notice(f"{board_id}-1", board_id=board_id)]

    result = notices.refresh_notices(fetch=fake_fetch)

    assert result["new"] == len(notices.SOURCES) - 1
    assert result["errors"][0]["board_id"] == "BBSMSTR_000000000090"
    assert "site down" in result["errors"][0]["error"]

    again = notices.refresh_notices(fetch=fake_fetch)
    assert again["new"] == 0


def test_refresh_with_saved_html(client):
    """Хадгалсан HTML-ийг ашиглан задлах → хадгалах бүтэн урсгал."""
    pages = {
        "BBSMSTR_000000000087": load("hanbat_087_notice.html"),
        "BBSMSTR_000000000090": load("hanbat_090_announcement.html"),
        "BBSMSTR_000000000050": load("hanbat_050_general.html"),
    }

    def fake_fetch(board_id):
        items = parse_notice_list(pages[board_id], board_id)
        return [item for item in items if is_relevant(item, notices.SOURCES[board_id]["keywords"])]

    result = notices.refresh_notices(fetch=fake_fetch)

    assert result["errors"] == []
    saved = notices.list_saved_notices(limit=100)
    assert len(saved) == result["new"] > 10
    assert any("토익경시대회" in item["title"] for item in saved)
    assert saved[0]["source"]
