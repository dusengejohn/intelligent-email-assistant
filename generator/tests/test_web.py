"""Tests for serving the built page from the API (story 3b.3, issue #82).

In the Docker image the page's build output sits in `static/`; FastAPI serves it
at `/`, next to the API under `/api` (same origin, no CORS, one container).
In dev and in these tests there is no `static/` unless a test creates one.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

INDEX = "<!doctype html><title>Email Generator</title>"


def web_dir(tmp_path: Path) -> Path:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text(INDEX)
    (static / "assets" / "app.js").write_text("console.log('hi')")
    return static


def test_page_is_served_at_the_root(tmp_path: Path) -> None:
    client = TestClient(create_app(web_dir(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Email Generator" in response.text


def test_built_assets_are_served(tmp_path: Path) -> None:
    client = TestClient(create_app(web_dir(tmp_path)))

    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert "console.log" in response.text


def test_api_still_wins_next_to_the_page(tmp_path: Path) -> None:
    client = TestClient(create_app(web_dir(tmp_path)))

    assert client.get("/api/health").json() == {"status": "ok"}


def test_unknown_api_path_is_a_json_404_not_the_page(tmp_path: Path) -> None:
    client = TestClient(create_app(web_dir(tmp_path)))

    for response in (client.get("/api/no-such-endpoint"), client.post("/api/generat")):
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}


def test_without_a_build_only_the_api_runs(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "missing"))

    assert client.get("/").status_code == 404
    assert client.get("/api/health").status_code == 200
