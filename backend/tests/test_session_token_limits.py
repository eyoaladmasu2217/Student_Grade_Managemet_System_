import logging
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.security import hash_password

PASSWORD = "a-secure-password"
CREDENTIALS = {"email": "learner@example.edu", "password": PASSWORD}


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
        assert test_client.post("/api/auth/login", json=CREDENTIALS).status_code == 200
        yield test_client, path


def test_oversized_cookie_is_rejected_and_logged(
    client, caplog: pytest.LogCaptureFixture
) -> None:
    test_client, path = client
    test_client.cookies.set("sgms_session", "x" * 512)

    with caplog.at_level(logging.WARNING, logger="sgms.security"):
        response = test_client.get("/api/auth/me")

    assert response.status_code == 401
    messages = [record.getMessage() for record in caplog.records if record.name == "sgms.security"]
    assert any("event=session outcome=failure" in message for message in messages)
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_oversized_cookie_does_not_revoke_the_real_session(client) -> None:
    test_client, _ = client
    real_token = test_client.cookies.get("sgms_session")
    test_client.cookies.set("sgms_session", "x" * 512)

    assert test_client.post("/api/auth/logout").status_code == 204

    test_client.cookies.set("sgms_session", real_token)
    assert test_client.get("/api/auth/me").status_code == 200
