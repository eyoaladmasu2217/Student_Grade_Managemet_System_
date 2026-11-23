import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
