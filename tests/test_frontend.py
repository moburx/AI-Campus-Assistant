"""FastAPI нь frontend файлуудыг зөв үйлчилж байгааг шалгана."""


def test_root_serves_index_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AI Campus" in response.text


def test_static_files_are_served(client):
    for path in ("/app.js", "/i18n.js", "/style.css"):
        assert client.get(path).status_code == 200, path


def test_api_routes_still_work(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api").json()["docs"] == "/docs"


def test_unknown_paths_return_404(client):
    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/missing-page.html").status_code == 404