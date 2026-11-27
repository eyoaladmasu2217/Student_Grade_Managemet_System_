import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.security import hash_password, hash_session_token

PASSWORD = "a-secure-password"


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    with TestClient(app) as test_client:
        with closing(sqlite3.connect(path)) as connection:
            connection.execute(
                "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
                ("learner@example.edu", "Learner", hash_password(PASSWORD), "student"),
            )
            connection.commit()
        yield test_client, path


def test_sign_in_replaces_the_presented_session(client) -> None:
    test_client, path = client
    credentials = {"email": "learner@example.edu", "password": PASSWORD}

    first = test_client.post("/api/auth/login", json=credentials)
    first_token = first.cookies.get("sgms_session")
    second = test_client.post("/api/auth/login", json=credentials)
    second_token = second.cookies.get("sgms_session")

    assert first_token and second_token and first_token != second_token
    with closing(sqlite3.connect(path)) as connection:
        hashes = {
            row[0] for row in connection.execute("SELECT token_hash FROM sessions")
        }
    assert hash_session_token(first_token) not in hashes
    assert hash_session_token(second_token) in hashes
    assert test_client.get("/api/auth/me").status_code == 200
