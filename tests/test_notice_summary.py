"""Мэдэгдлийг AI-аар тайлбарлах хэсгийн тест.

Сургуулийн сайт, Gemini хоёрын аль алинд нь хүсэлт илгээхгүй:
хадгалсан HTML болон хуурамч функц ашиглана.
"""

from pathlib import Path

import httpx
import pytest

from backend import notice_summary, notices
from backend.database import get_connection
from backend.notice_summary import parse_notice_detail

FIXTURES = Path(__file__).parent / "fixtures"
VIEW_HTML = (FIXTURES / "hanbat_087_view.html").read_text(encoding="utf-8")


def add_notice(ntt_id="B000000171040Nt4iC3a", title="제33회 토익경시대회 모집(장학금10~30만원)"):
    board = "BBSMSTR_000000000087"
    with get_connection() as connection:
        notices.save_notices(connection, [{
            "board_id": board,
            "ntt_id": ntt_id,
            "title": title,
            "writer": "국제교류원",
            "posted_at": "2026-10-12",
            "pinned": False,
            "is_new": False,
            "url": notices.notice_url(board, ntt_id),
        }])
    return notices.list_saved_notices()[0]["id"]


# ---------- Нийтлэлийн хуудас задлах ----------
def test_parse_notice_detail():
    detail = parse_notice_detail(VIEW_HTML)

    assert detail["title"] == "제33회 토익경시대회 모집(장학금10~30만원)"
    assert "H-CAN" in detail["body"]
    assert "첨부파일" in detail["body"]
    # Хуудасны доод хэсэг (хаяг, зохиогчийн эрх) агуулгад орохгүй.
    assert "Copyright" not in detail["body"]
    assert "공공누리" not in detail["body"]
    assert len(detail["attachments"]) == 3
    assert detail["attachments"][0].startswith("1. 제33회 국립한밭대학교 토익경시대회")
    assert detail["images"] == [
        "https://www.hanbat.ac.kr/namo/binary/images/000228/20261012101322420_YTDW56YV.jpg"
    ]


def test_parse_detail_ignores_images_from_other_sites():
    html = """
    <h2 class="ui bbs--view--tit">T</h2>
    <div class="ui bbs--view--content">
      <p>본문</p>
      <img src="/namo/a.jpg">
      <img src="https://evil.example.com/b.jpg">
    </div>"""
    detail = parse_notice_detail(html)
    assert detail["images"] == ["https://www.hanbat.ac.kr/namo/a.jpg"]
    assert detail["body"] == "본문"


def test_fetch_notice_detail_downloads_poster():
    def handler(request):
        if request.url.path.endswith("view.do"):
            return httpx.Response(200, text=VIEW_HTML)
        return httpx.Response(200, content=b"\xff\xd8fakejpeg", headers={"content-type": "image/jpeg"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    detail = notice_summary.fetch_notice_detail(
        "https://www.hanbat.ac.kr/bbs/BBSMSTR_000000000087/view.do?nttId=X", client=client
    )

    assert detail["image_data"] == [{"mime_type": "image/jpeg", "data": b"\xff\xd8fakejpeg"}]


def test_fetch_notice_detail_skips_non_images():
    def handler(request):
        if request.url.path.endswith("view.do"):
            return httpx.Response(200, text=VIEW_HTML)
        return httpx.Response(200, text="<html>not an image</html>", headers={"content-type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    detail = notice_summary.fetch_notice_detail("https://www.hanbat.ac.kr/x/view.do", client=client)
    assert detail["image_data"] == []


def test_summary_message_contains_notice_data():
    detail = parse_notice_detail(VIEW_HTML)
    detail["image_data"] = [{"mime_type": "image/jpeg", "data": b"x"}]
    notice = {"title": "T", "posted_at": "2026-10-12", "source": "국제교류원 Notice"}

    message = notice_summary.build_summary_message(notice, detail, "mn")

    assert "reply_language: mn" in message
    assert "H-CAN" in message
    assert "대회 참가신청서" in message
    assert "poster_images_attached: 1" in message


# ---------- Хадгалах (cache) ----------
def test_summary_is_cached_per_language(client):
    notice_id = add_notice()
    calls = []

    def fake_fetch(url):
        return {"title": "T", "body": "B", "attachments": [], "images": [], "image_data": []}

    def fake_summarize(notice, detail, language):
        calls.append(language)
        return f"summary in {language}"

    first = notice_summary.get_or_create_summary(notice_id, "mn", fake_fetch, fake_summarize)
    second = notice_summary.get_or_create_summary(notice_id, "mn", fake_fetch, fake_summarize)
    korean = notice_summary.get_or_create_summary(notice_id, "ko", fake_fetch, fake_summarize)

    assert first == {"summary": "summary in mn", "language": "mn", "cached": False, "url": first["url"]}
    assert second["cached"] is True
    assert korean["summary"] == "summary in ko"
    assert calls == ["mn", "ko"]


def test_summary_for_missing_notice(client):
    with pytest.raises(notice_summary.NotFoundError):
        notice_summary.get_or_create_summary(9999, "mn")


def test_summarize_without_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(notice_summary.AIUnavailableError):
        notice_summary.summarize_with_gemini({}, {}, "mn")


# ---------- API ----------
def test_summary_api_uses_profile_language(client, make_user, monkeypatch):
    headers = make_user("bolor", language="mn")
    notice_id = add_notice()
    seen = {}

    def fake(notice_id_arg, language):
        seen["language"] = language
        return {"summary": "- Тайлбар", "language": language, "cached": False, "url": "u"}

    monkeypatch.setattr(notice_summary, "get_or_create_summary", fake)

    response = client.post(f"/api/notices/{notice_id}/summary", headers=headers)

    assert response.status_code == 200
    assert response.json()["summary"] == "- Тайлбар"
    assert seen["language"] == "mn"


def test_summary_api_language_override(client, user_headers, monkeypatch):
    notice_id = add_notice()
    monkeypatch.setattr(
        notice_summary,
        "get_or_create_summary",
        lambda notice_id_arg, language: {"summary": language, "language": language, "cached": True, "url": "u"},
    )

    assert client.post(f"/api/notices/{notice_id}/summary?language=vi", headers=user_headers).json()["summary"] == "vi"
    assert client.post(f"/api/notices/{notice_id}/summary?language=fr", headers=user_headers).status_code == 422


def test_summary_api_errors(client, user_headers, monkeypatch):
    assert client.post("/api/notices/1/summary").status_code in (401, 403)
    assert client.post("/api/notices/9999/summary", headers=user_headers).status_code == 404

    notice_id = add_notice()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(
        notice_summary,
        "fetch_notice_detail",
        lambda url: {"title": "T", "body": "B", "attachments": [], "images": [], "image_data": []},
    )
    assert client.post(f"/api/notices/{notice_id}/summary", headers=user_headers).status_code == 503

    def broken(url):
        raise httpx.ConnectError("school site down")

    monkeypatch.setattr(notice_summary, "fetch_notice_detail", broken)
    assert client.post(f"/api/notices/{notice_id}/summary", headers=user_headers).status_code == 502


# ---------- Gemini хариу (хуурамч client) ----------
class FakeGeminiClient:
    def __init__(self, response):
        self.response = response
        self.requests = []
        self.models = type("Models", (), {"generate_content": self.generate_content})()

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        return self.response


def gemini_response(text, finish_reason="STOP"):
    types = pytest.importorskip("google.genai.types")
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        finish_reason=finish_reason,
    )])


SAMPLE_DETAIL = {"title": "T", "body": "B", "attachments": [], "images": [], "image_data": []}
SAMPLE_NOTICE = {"title": "T", "posted_at": "2026-10-12", "source": "국제교류원 Notice"}


def test_summarize_returns_text_and_sends_poster():
    fake = FakeGeminiClient(gemini_response("- Тайлбар"))
    detail = dict(SAMPLE_DETAIL, image_data=[{"mime_type": "image/jpeg", "data": b"img"}])

    text = notice_summary.summarize_with_gemini(SAMPLE_NOTICE, detail, "mn", client=fake)

    assert text == "- Тайлбар"
    parts = fake.requests[0]["contents"][0].parts
    assert "reply_language: mn" in parts[0].text
    assert parts[1].inline_data.mime_type == "image/jpeg"
    assert fake.requests[0]["config"].max_output_tokens == notice_summary.MAX_OUTPUT_TOKENS


def test_cut_off_summary_is_not_saved(client):
    """MAX_TOKENS-оор тасарсан хариу алдаа болж, DB-д хадгалагдахгүй."""
    notice_id = add_notice()
    fake = FakeGeminiClient(gemini_response("- Шагнал, урамшуулал:", finish_reason="MAX_TOKENS"))

    with pytest.raises(notice_summary.AIUnavailableError):
        notice_summary.get_or_create_summary(
            notice_id,
            "mn",
            fetch_detail=lambda url: SAMPLE_DETAIL,
            summarize=lambda notice, detail, language: notice_summary.summarize_with_gemini(
                notice, detail, language, client=fake
            ),
        )

    assert notice_summary.get_cached_summary(notice_id, "mn") is None
