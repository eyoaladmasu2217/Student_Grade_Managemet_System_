import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app import database
from app.config import ConfigurationError
from app.main import create_app
from app.request_limits import limit_request_body, max_request_bytes
from app.security_headers import SECURITY_HEADERS


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_MAX_REQUEST_BYTES", "1024")
    app = FastAPI()
    app.middleware("http")(limit_request_body)

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        return {"bytes": len(await request.body())}

    with TestClient(app) as test_client:
        yield test_client


def test_body_under_the_limit_is_forwarded(client: TestClient) -> None:
    response = client.post("/echo", json={"value": "ok"})

    assert response.status_code == 200
    assert response.json()["bytes"] > 0


def test_declared_oversized_body_is_rejected(client: TestClient) -> None:
    response = client.post("/echo", content=b"x" * 2000)

    assert response.status_code == 413
    assert "exceeds 1024 bytes" in response.json()["detail"]


def test_invalid_content_length_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/echo", content=b"ok", headers={"content-length": "not-a-number"}
    )

    assert response.status_code == 413


@pytest.mark.parametrize("value", ["0", "12", "not-a-number"])
def test_invalid_limits_fail_at_startup(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SGMS_MAX_REQUEST_BYTES", value)

    with pytest.raises(ConfigurationError):
        max_request_bytes()


def test_rejected_bodies_get_security_headers(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SGMS_MAX_REQUEST_BYTES", "1024")
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.sqlite3")

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/auth/login",
            content=b"x" * 2000,
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 413
    for name, value in SECURITY_HEADERS.items():
        assert response.headers.get(name) == value
