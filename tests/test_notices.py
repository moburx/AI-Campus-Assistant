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
