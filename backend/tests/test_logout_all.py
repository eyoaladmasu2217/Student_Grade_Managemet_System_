from contextlib import closing
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.security import hash_password

EMAIL = "student@example.edu"
PASSWORD = "a-secure-password"


@pytest.fixture
def db_path(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    with TestClient(app):
        with closing(sqlite3.connect(path)) as connection:
            connection.execute(
                "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
                (EMAIL, "Student", hash_password(PASSWORD), "student"),
            )
            connection.commit()
    return path


def sign_in() -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 200
    return client


def test_logout_all_revokes_every_device(db_path) -> None:
    first = sign_in()
    second = sign_in()
    assert first.get("/api/auth/me").status_code == 200
    assert second.get("/api/auth/me").status_code == 200

    response = first.post("/api/auth/logout-all")

    assert response.status_code == 204
    assert first.get("/api/auth/me").status_code == 401
    assert second.get("/api/auth/me").status_code == 401
    with closing(sqlite3.connect(db_path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_login_still_works_after_logout_all(db_path) -> None:
    client = sign_in()
    assert client.post("/api/auth/logout-all").status_code == 204

    assert sign_in().get("/api/auth/me").status_code == 200
