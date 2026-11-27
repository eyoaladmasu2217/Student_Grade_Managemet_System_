import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import database
from app.main import create_app
from app.security_headers import HSTS_VALUE, SECURITY_HEADERS, add_security_headers


@pytest.fixture
def client():
    app = FastAPI()
    app.middleware("http")(add_security_headers)

    @app.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as test_client:
        yield test_client


def test_responses_include_security_headers(client: TestClient) -> None:
    response = client.get("/ping")

    assert response.status_code == 200
    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value


def test_hsts_is_only_added_for_https_requests(client: TestClient) -> None:
    assert "strict-transport-security" not in client.get("/ping").headers

    https_client = TestClient(client.app, base_url="https://example.edu")
    response = https_client.get("/ping")

    assert response.headers["strict-transport-security"] == HSTS_VALUE


def test_csrf_rejections_still_get_security_headers(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SGMS_FRONTEND_ORIGINS", "https://grades.example.edu")
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.sqlite3")

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.edu", "password": "wrong-password"},
            headers={"origin": "https://attacker.example"},
        )

    assert response.status_code == 403
    for name, value in SECURITY_HEADERS.items():
        assert response.headers.get(name) == value
