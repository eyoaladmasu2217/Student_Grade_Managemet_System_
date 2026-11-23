import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.csrf import validate_request_origin


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_FRONTEND_ORIGINS", "https://grades.example.edu")
    app = FastAPI()
    app.middleware("http")(validate_request_origin)

    @app.post("/action")
    def action() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/action")
    def read_action() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as test_client:
        yield test_client


def test_non_browser_requests_are_allowed(client: TestClient) -> None:
    assert client.post("/action").status_code == 200


def test_allowlisted_origin_is_allowed(client: TestClient) -> None:
    response = client.post(
        "/action",
        headers={
            "origin": "https://grades.example.edu",
            "x-requested-with": "XMLHttpRequest",
        },
    )

    assert response.status_code == 200


def test_unknown_origin_is_rejected(client: TestClient) -> None:
    response = client.post("/action", headers={"origin": "https://attacker.example"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Request origin is not allowed"


def test_browser_requests_need_the_custom_header(client: TestClient) -> None:
    response = client.post("/action", headers={"origin": "https://grades.example.edu"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Browser state changes require a custom request header"


def test_cross_site_fetch_is_rejected_even_with_valid_origin(client: TestClient) -> None:
    response = client.post(
        "/action",
        headers={
            "origin": "https://grades.example.edu",
            "sec-fetch-site": "cross-site",
            "x-requested-with": "XMLHttpRequest",
        },
    )

    assert response.status_code == 403


def test_same_origin_fetch_is_allowed(client: TestClient) -> None:
    response = client.post(
        "/action",
        headers={
            "origin": "https://grades.example.edu",
            "sec-fetch-site": "same-origin",
            "x-requested-with": "XMLHttpRequest",
        },
    )

    assert response.status_code == 200


def test_safe_methods_ignore_origin(client: TestClient) -> None:
    response = client.get("/action", headers={"origin": "https://attacker.example"})

    assert response.status_code == 200
