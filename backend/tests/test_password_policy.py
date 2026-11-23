from contextlib import closing
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.password_policy import validate_password
from app.security import hash_password

PASSWORD = "a-secure-password"


@pytest.mark.parametrize(
    ("password", "email"),
    [
        ("password123456", None),
        ("abcd-secure-code", None),
        ("student-secure-pass", "student@example.edu"),
        ("aaaaaaaaaaaa", None),
    ],
)
def test_weak_passwords_are_rejected(password: str, email: str | None) -> None:
    with pytest.raises(ValueError):
        validate_password(password, email)


def test_strong_password_is_accepted() -> None:
    assert validate_password("a-secure-password", "teacher@example.edu") == "a-secure-password"


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
        assert test_client.post(
            "/api/auth/login", json={"email": "admin@example.edu", "password": PASSWORD}
        ).status_code == 200
        yield test_client


def test_admin_cannot_create_user_with_weak_password(client: TestClient) -> None:
    response = client.post(
        "/api/users",
        json={
            "email": "new.student@example.edu",
            "full_name": "New Student",
            "password": "password123456",
            "role": "student",
        },
    )

    assert response.status_code == 422


def test_password_change_rejects_email_derived_password(client: TestClient) -> None:
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "admin-secure-password"},
    )

    assert response.status_code == 422
    assert "email name" in response.json()["detail"]
