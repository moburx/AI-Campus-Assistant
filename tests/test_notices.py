"""공지사항 수집기 테스트.

Сургуулийн сайт руу хүсэлт илгээхгүйн тулд tests/fixtures/ дотор
хадгалсан HTML-ээр шалгана.
"""

from pathlib import Path

import httpx
import pytest

from backend import notices
from backend.database import get_connection
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


def test_fetch_board_uses_page_and_tags_international(monkeypatch):
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
    # Бүгдийг буцаана, харин түлхүүр үгтэйг нь л "international" гэж тэмдэглэнэ.
    assert len(items) > 1
    tagged = [item for item in items if item["international"]]
    assert len(tagged) == 1
    assert "천원의 아침밥" in tagged[0]["title"]


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
        if board_id == "BBSMSTR_000000000042":
            raise RuntimeError("site down")
        return [sample_notice(f"{board_id}-1", board_id=board_id)]

    result = notices.refresh_notices(fetch=fake_fetch)

    assert result["new"] == len(notices.SOURCES) - 1
    assert result["errors"][0]["board_id"] == "BBSMSTR_000000000042"
    assert "site down" in result["errors"][0]["error"]

    again = notices.refresh_notices(fetch=fake_fetch)
    assert again["new"] == 0


def test_refresh_with_saved_html(client):
    """Хадгалсан HTML-ийг ашиглан задлах → хадгалах бүтэн урсгал."""
    pages = {
        "BBSMSTR_000000000087": load("hanbat_087_notice.html"),
        # 학사공지 (042) нь ерөнхий самбартай ижил HTML бүтэцтэй тул 090-ийн хадгалсан хуудсыг ашиглана.
        "BBSMSTR_000000000042": load("hanbat_090_announcement.html"),
        "BBSMSTR_000000000050": load("hanbat_050_general.html"),
    }

    def fake_fetch(board_id):
        items = parse_notice_list(pages[board_id], board_id)
        return [notices.tag_international(item, board_id) for item in items]

    result = notices.refresh_notices(fetch=fake_fetch)

    assert result["errors"] == []
    saved = notices.list_saved_notices(limit=100)
    assert len(saved) == result["new"] > 10
    assert any("토익경시대회" in item["title"] for item in saved)
    assert saved[0]["source"]
    # Ерөнхий самбарын мэдэгдлийг бүгдийг нь хадгалж, зарим нь л "гадаад оюутанд".
    assert any(not item["international"] for item in saved)
    assert {item["category"] for item in saved} == {"international", "academic", "general"}


# ---------- Олон хуудас, "гадаад оюутанд" тэмдэг ----------
@pytest.mark.parametrize(
    "title, expected",
    [
        ("2026학년도 2학기 장학금 신청 안내", True),
        ("TOPIK 시험 접수 안내", True),
        ("기숙사 입사 신청", True),
        ("Global Buddy Program", True),
        ("2학기 수강신청 일정 안내", False),
        ("도서관 휴관 안내", False),
    ],
)
def test_general_board_tags_international_by_keyword(title, expected):
    notice = notices.tag_international({"title": title}, "BBSMSTR_000000000050")
    assert notice["international"] is expected


def test_international_boards_tag_everything():
    notice = notices.tag_international({"title": "도서관 휴관 안내"}, "BBSMSTR_000000000087")
    assert notice["international"] is True


def test_fetch_recent_reads_several_pages_politely():
    pages = {
        "1": load("hanbat_050_general.html"),
        "2": load("hanbat_087_notice.html"),
        "3": load("hanbat_090_announcement.html"),
    }
    requested = []
    sleeps = []

    def handler(request):
        page = request.url.params["pageIndex"]
        requested.append(page)
        return httpx.Response(200, text=pages[page])

    client = httpx.Client(transport=httpx.MockTransport(handler))

    items = notices.fetch_recent("BBSMSTR_000000000050", pages=3, client=client, sleep=sleeps.append)

    assert requested == ["1", "2", "3"]
    assert sleeps == [notices.PAGE_DELAY_SECONDS, notices.PAGE_DELAY_SECONDS]
    ids = [item["ntt_id"] for item in items]
    assert len(ids) == len(set(ids))
    assert len(items) > len(parse_notice_list(pages["1"], "X"))


def test_fetch_recent_stops_when_a_page_has_nothing_new():
    html = load("hanbat_087_notice.html")
    requested = []

    def handler(request):
        requested.append(request.url.params["pageIndex"])
        return httpx.Response(200, text=html)  # хуудас бүр ижил = шинэ мэдэгдэл алга

    client = httpx.Client(transport=httpx.MockTransport(handler))

    notices.fetch_recent("BBSMSTR_000000000087", pages=3, client=client, sleep=lambda seconds: None)

    assert requested == ["1", "2"]


def test_list_can_show_only_international(client):
    with get_connection() as connection:
        notices.save_notices(connection, [
            {**sample_notice("A", title="장학금 안내", board_id="BBSMSTR_000000000050"), "international": True},
            {**sample_notice("B", title="수강신청 안내", board_id="BBSMSTR_000000000050"), "international": False},
        ])

    everything = notices.list_saved_notices()
    only_international = notices.list_saved_notices(international_only=True)

    assert {item["title"] for item in everything} == {"장학금 안내", "수강신청 안내"}
    assert [item["title"] for item in only_international] == ["장학금 안내"]
    assert only_international[0]["international"] is True


def test_retagging_on_refresh_updates_saved_notice(client):
    item = {**sample_notice("A", title="안내", board_id="BBSMSTR_000000000050"), "international": False}
    with get_connection() as connection:
        notices.save_notices(connection, [item])
        notices.save_notices(connection, [{**item, "international": True}])

    assert notices.list_saved_notices(international_only=True)[0]["title"] == "안내"


@pytest.mark.parametrize(
    "title",
    ["하계 해외연수 참가자 모집", "모의 어학시험 접수 안내", "외국어 능력 향상 프로그램"],
)
def test_outbound_programs_are_not_tagged_for_international_students(title):
    # 해외 / 어학 / 외국어 нь Солонгос оюутны гадаад хөтөлбөрийг татдаг тул түлхүүр үгэнд байхгүй.
    assert notices.tag_international({"title": title}, "BBSMSTR_000000000050")["international"] is False


@pytest.mark.parametrize(
    "title",
    ["외국인등록증 발급 안내", "D-2 유학생 시간제취업 허가 신청", "외국인 건강보험 가입 안내", "생활관 입사 신청"],
)
def test_new_keywords_for_international_students(title):
    assert notices.tag_international({"title": title}, "BBSMSTR_000000000042")["international"] is True


def test_removed_board_is_hidden_and_academic_category(client):
    with get_connection() as connection:
        notices.save_notices(connection, [
            sample_notice("OLD", title="2024 모의토익", board_id="BBSMSTR_000000000090"),
            {**sample_notice("ACA", title="계절학기 안내", board_id="BBSMSTR_000000000042"), "international": False},
        ])

    titles = [item["title"] for item in notices.list_saved_notices()]
    academic = notices.list_saved_notices(category="academic")

    assert "2024 모의토익" not in titles
    assert [item["title"] for item in academic] == ["계절학기 안내"]
    assert academic[0]["category"] == "academic"
