from contextlib import closing
import logging
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.audit import log_security_event
from app.main import app
from app.security import hash_password

PASSWORD = "a-secure-password"


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.sqlite3")
    with TestClient(app) as test_client:
        with closing(sqlite3.connect(tmp_path / "test.sqlite3")) as connection:
            connection.execute(
                "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
                ("admin@example.edu", "Admin", hash_password(PASSWORD), "admin"),
            )
            connection.commit()
        yield test_client


def security_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == "sgms.security"]


def test_failed_login_is_logged_without_the_password(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="sgms.security"):
        response = client.post(
            "/api/auth/login",
            json={"email": "admin@example.edu", "password": "never-log-this-password"},
        )

    assert response.status_code == 401
    messages = security_messages(caplog)
    assert any("event=login outcome=failure" in message for message in messages)
    assert all("never-log-this-password" not in message for message in messages)


def test_successful_login_is_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="sgms.security"):
        client.post(
            "/api/auth/login", json={"email": "admin@example.edu", "password": PASSWORD}
        )

    assert any("event=login outcome=success" in message for message in security_messages(caplog))


def test_admin_user_creation_is_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    client.post("/api/auth/login", json={"email": "admin@example.edu", "password": PASSWORD})
    with caplog.at_level(logging.INFO, logger="sgms.security"):
        response = client.post(
            "/api/users",
            json={
                "email": "new@example.edu",
                "full_name": "New User",
                "password": "another-secure-password",
                "role": "student",
            },
        )

    assert response.status_code == 201
    messages = security_messages(caplog)
    assert any("event=user_created outcome=success" in message for message in messages)
    assert all("another-secure-password" not in message for message in messages)


def test_log_details_are_single_line(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="sgms.security"):
        log_security_event("test_event", "success", detail="first\nsecond")

    message = security_messages(caplog)[0]
    assert "first\\\\nsecond" in message
    assert "\n" not in message
