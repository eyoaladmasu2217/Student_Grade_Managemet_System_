import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.security import hash_password


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.sqlite3")
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_sets_http_only_session_cookie(client: TestClient, tmp_path) -> None:
    with sqlite3.connect(tmp_path / "test.sqlite3") as connection:
        connection.execute(
            "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
            ("teacher@example.edu", "Teacher", hash_password("a-secure-password"), "instructor"),
        )

    response = client.post(
        "/api/auth/login",
        json={"email": "teacher@example.edu", "password": "a-secure-password"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "instructor"
    assert response.cookies.get("sgms_session")
    assert "httponly" in response.headers["set-cookie"].lower()


def test_login_rejects_wrong_password(client: TestClient, tmp_path) -> None:
    with sqlite3.connect(tmp_path / "test.sqlite3") as connection:
        connection.execute(
            "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
            ("teacher@example.edu", "Teacher", hash_password("a-secure-password"), "instructor"),
        )

    response = client.post(
        "/api/auth/login",
        json={"email": "teacher@example.edu", "password": "incorrect-password"},
    )

    assert response.status_code == 401
