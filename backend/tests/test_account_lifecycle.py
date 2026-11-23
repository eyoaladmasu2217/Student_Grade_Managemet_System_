from contextlib import closing
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.security import hash_password

PASSWORD = "a-secure-password"


@pytest.fixture
def clients(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    with TestClient(app) as admin:
        with closing(sqlite3.connect(path)) as connection:
            connection.executemany(
                "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
                [
                    ("admin@example.edu", "Admin", hash_password(PASSWORD), "admin"),
                    ("student@example.edu", "Student", hash_password(PASSWORD), "student"),
                ],
            )
            connection.commit()
        assert admin.post(
            "/api/auth/login",
            json={"email": "admin@example.edu", "password": PASSWORD},
        ).status_code == 200
        student = TestClient(app)
        assert student.post(
            "/api/auth/login",
            json={"email": "student@example.edu", "password": PASSWORD},
        ).status_code == 200
        with closing(sqlite3.connect(path)) as connection:
            ids = dict(
                connection.execute("SELECT email, id FROM users").fetchall()
            )
        yield admin, student, ids


def test_admin_can_deactivate_and_reactivate_an_account(clients) -> None:
    admin, student, ids = clients
    student_id = ids["student@example.edu"]

    deactivated = admin.patch(f"/api/users/{student_id}/active", json={"is_active": False})
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert student.get("/api/auth/me").status_code == 401
    assert student.post(
        "/api/auth/login",
        json={"email": "student@example.edu", "password": PASSWORD},
    ).status_code == 401

    reactivated = admin.patch(f"/api/users/{student_id}/active", json={"is_active": True})
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True
    assert student.post(
        "/api/auth/login",
        json={"email": "student@example.edu", "password": PASSWORD},
    ).status_code == 200


def test_admin_cannot_deactivate_self(clients) -> None:
    admin, _, ids = clients

    response = admin.patch(
        f"/api/users/{ids['admin@example.edu']}/active", json={"is_active": False}
    )

    assert response.status_code == 400
    assert admin.get("/api/auth/me").status_code == 200


def test_non_admin_cannot_change_account_status(clients) -> None:
    _, student, ids = clients

    response = student.patch(
        f"/api/users/{ids['admin@example.edu']}/active", json={"is_active": False}
    )

    assert response.status_code == 403


def test_unknown_account_returns_not_found(clients) -> None:
    admin, _, _ = clients

    assert admin.patch("/api/users/9999/active", json={"is_active": False}).status_code == 404
