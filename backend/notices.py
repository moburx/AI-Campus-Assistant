"""한밭대 공지사항 게시판 수집기 (Hanbat notice board scraper).

Сургуулийн нийтэд нээлттэй самбаруудын жагсаалтын хуудсыг татаж,
гарчиг, огноо, бичсэн хэлтэс, нийтлэлийн холбоосыг гаргаж авна.

- robots.txt: /bbs/ замыг хориглоогүй (зөвхөн /search/ хориотой).
- Сайтыг ачааллахгүйн тулд зөвхөн эхний хуудсыг, ховор (хэдэн цагт нэг) уншина.
- Python-ы стандарт html.parser ашигладаг тул нэмэлт сан шаардлагагүй.
"""

import re
from datetime import datetime, timezone
from html.parser import HTMLParser

from backend.database import get_connection

BASE_URL = "https://www.hanbat.ac.kr"
USER_AGENT = "AI-Campus-Assistant/1.0 (student project; notice reader)"
REQUEST_TIMEOUT_SECONDS = 15

# Унших самбарууд. keywords хоосон бол бүх мэдэгдлийг авна.
SOURCES = {
    "BBSMSTR_000000000087": {
        "name": "국제교류원 Notice",
        "keywords": [],
    },
    "BBSMSTR_000000000090": {
        "name": "국제교류원 Announcement",
        "keywords": [],
    },
    "BBSMSTR_000000000050": {
        "name": "한밭대 공지사항",
        "keywords": ["외국인", "유학생", "국제", "international", "global", "글로벌", "visa", "비자"],
    },
}

DETAIL_ID_PATTERN = re.compile(r"fn_search_detail\('([^']+)'\)")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def notice_url(board_id: str, ntt_id: str) -> str:
    return f"{BASE_URL}/bbs/{board_id}/view.do?nttId={ntt_id}"


def list_url(board_id: str, page: int = 1) -> str:
    return f"{BASE_URL}/bbs/{board_id}/list.do?pageIndex={page}"


class NoticeListParser(HTMLParser):
    """<tbody> доторх мөр бүрээс гарчиг, ID, бичсэн хэлтэс, огноог цуглуулна."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._in_tbody = False
        self._row = None
        self._cell = None      # одоо уншиж буй нүдний класс (subject, writer, regDate)
        self._in_title_link = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "tbody":
            self._in_tbody = True
        elif not self._in_tbody:
            return
        elif tag == "tr":
            self._row = {
                "title": "",
                "writer": "",
                "date": "",
                "ntt_id": None,
                "pinned": "notice" in (attrs.get("class") or "").split(),
                "is_new": False,
            }
        elif self._row is None:
            return
        elif tag == "td":
            self._cell = (attrs.get("class") or "").split()[0] if attrs.get("class") else None
        elif tag == "a" and self._cell == "subject":
            match = DETAIL_ID_PATTERN.search(attrs.get("onclick") or "")
            if match:
                self._row["ntt_id"] = match.group(1)
                self._in_title_link = True
        elif tag == "span" and "ir-bbs-new" in (attrs.get("class") or ""):
            self._row["is_new"] = True

    def handle_endtag(self, tag):
        if tag == "tbody":
            self._in_tbody = False
        elif tag == "a":
            self._in_title_link = False
        elif tag == "td":
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row["ntt_id"] and self._row["title"]:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._row is None:
            return

        text = data.strip()
        if not text:
            return

        if self._in_title_link:
            self._row["title"] = f"{self._row['title']} {text}".strip()
        elif self._cell == "writer":
            self._row["writer"] = text
        elif self._cell == "regDate" and DATE_PATTERN.fullmatch(text):
            self._row["date"] = text


def parse_notice_list(html: str, board_id: str) -> list:
    """Жагсаалтын HTML-ээс мэдэгдлүүдийг гаргана. Давхардсан (бэхлэгдсэн) мөрийг нэг л удаа."""
    parser = NoticeListParser()
    parser.feed(html)

    notices = []
    seen = set()
    for row in parser.rows:
        if row["ntt_id"] in seen:
            continue
        seen.add(row["ntt_id"])
        notices.append({
            "board_id": board_id,
            "ntt_id": row["ntt_id"],
            "title": " ".join(row["title"].split()),
            "writer": row["writer"],
            "posted_at": row["date"],
            "pinned": row["pinned"],
            "is_new": row["is_new"],
            "url": notice_url(board_id, row["ntt_id"]),
        })

    return notices


def is_relevant(notice: dict, keywords: list) -> bool:
    """Түлхүүр үг байхгүй бол бүгд хамаатай, байвал гарчигт нэг нь орсон эсэх."""
    if not keywords:
        return True

    title = notice["title"].lower()
    return any(keyword.lower() in title for keyword in keywords)


def fetch_board(board_id: str, page: int = 1, client=None) -> list:
    """Самбарын нэг хуудсыг татаж, хамаатай мэдэгдлүүдийг буцаана."""
    import httpx

    source = SOURCES.get(board_id, {"keywords": []})
    owns_client = client is None
    client = client or httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
    )

    try:
        response = client.get(list_url(board_id, page))
        response.raise_for_status()
    finally:
        if owns_client:
            client.close()

    notices = parse_notice_list(response.text, board_id)
    return [notice for notice in notices if is_relevant(notice, source["keywords"])]


# ---------- DB-д хадгалах ----------
def save_notices(connection, items: list) -> int:
    """Мэдэгдлүүдийг хадгалж, ШИНЭЭР нэмэгдсэн тоог буцаана.

    Ижил (board_id, ntt_id) аль хэдийн байвал давхар хадгалахгүй,
    харин гарчиг эсвэл бэхлэгдсэн төлөв өөрчлөгдсөн бол шинэчилнэ.
    """
    new_count = 0

    for item in items:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO notices (
                board_id, ntt_id, title, writer, posted_at, pinned, url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["board_id"],
                item["ntt_id"],
                item["title"],
                item["writer"],
                item["posted_at"],
                int(item["pinned"]),
                item["url"],
            ),
        )

        if cursor.rowcount:
            new_count += 1
        else:
            connection.execute(
                """
                UPDATE notices SET title = ?, pinned = ?
                WHERE board_id = ? AND ntt_id = ?
                """,
                (item["title"], int(item["pinned"]), item["board_id"], item["ntt_id"]),
            )

    return new_count


LAST_REFRESH_KEY = "notices_last_refreshed"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_last_refreshed():
    """Мэдэгдлийг сүүлд татсан цаг (UTC, ISO хэлбэр) эсвэл None."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT value FROM app_meta WHERE key = ?",
            (LAST_REFRESH_KEY,),
        ).fetchone()

    return row["value"] if row else None


def set_last_refreshed(moment: datetime):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO app_meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (LAST_REFRESH_KEY, moment.isoformat(timespec="seconds")),
        )


def seconds_since_last_refresh(now: datetime = None):
    last = get_last_refreshed()
    if last is None:
        return None

    now = now or utc_now()
    return (now - datetime.fromisoformat(last)).total_seconds()


def refresh_notices(fetch=None) -> dict:
    """Бүх эх сурвалжийг татаж хадгална. Нэг самбар алдаа өгсөн ч бусдыг үргэлжлүүлнэ."""
    fetch = fetch or fetch_board
    result = {"fetched": 0, "new": 0, "errors": []}
    set_last_refreshed(utc_now())

    for board_id in SOURCES:
        try:
            items = fetch(board_id)
        except Exception as error:
            result["errors"].append({"board_id": board_id, "error": str(error)})
            continue

        with get_connection() as connection:
            result["new"] += save_notices(connection, items)
        result["fetched"] += len(items)

    return result


def notice_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "board_id": row["board_id"],
        "source": SOURCES.get(row["board_id"], {}).get("name", row["board_id"]),
        "title": row["title"],
        "writer": row["writer"],
        "posted_at": row["posted_at"],
        "pinned": bool(row["pinned"]),
        "url": row["url"],
    }


def list_saved_notices(limit: int = 50) -> list:
    """Хадгалсан мэдэгдлүүдийг шинэ нь эхэнд байхаар буцаана."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, board_id, title, writer, posted_at, pinned, url
            FROM notices
            ORDER BY posted_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [notice_to_dict(row) for row in rows]
