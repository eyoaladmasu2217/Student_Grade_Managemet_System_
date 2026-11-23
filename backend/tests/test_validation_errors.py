from contextlib import closing
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
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


def test_login_validation_does_not_echo_the_password(client: TestClient) -> None:
    password = "x" * 300

    response = client.post(
        "/api/auth/login", json={"email": "admin@example.edu", "password": password}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Email or password is not acceptable"}
    assert password not in response.text


def test_login_validation_does_not_echo_the_email(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"email": "not-an-email", "password": PASSWORD}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Email or password is not acceptable"}


def test_general_validation_errors_omit_rejected_input(client: TestClient) -> None:
    client.post("/api/auth/login", json={"email": "admin@example.edu", "password": PASSWORD})

    response = client.post(
        "/api/academic-years",
        json={"name": "year", "start_date": "2027-01-01", "end_date": "2026-01-01"},
    )

    assert response.status_code == 422
    assert "input" not in response.text
