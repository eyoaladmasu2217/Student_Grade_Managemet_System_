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


def create_user(client: TestClient, db_path, role: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
            (f"{role}@example.edu", role.title(), hash_password("a-secure-password"), role),
        )
    response = client.post(
        "/api/auth/login",
        json={"email": f"{role}@example.edu", "password": "a-secure-password"},
    )
    assert response.status_code == 200


def test_admin_can_create_academic_year_and_term(client: TestClient, tmp_path) -> None:
    create_user(client, tmp_path / "test.sqlite3", "admin")
    year_response = client.post(
        "/api/academic-years",
        json={
            "name": "2026-2027",
            "start_date": "2026-09-01",
            "end_date": "2027-06-30",
        },
    )

    assert year_response.status_code == 201
    year_id = year_response.json()["id"]
    term_response = client.post(
        f"/api/academic-years/{year_id}/terms",
        json={
            "name": "Fall",
            "start_date": "2026-09-01",
            "end_date": "2026-12-20",
        },
    )

    assert term_response.status_code == 201
    assert term_response.json()["academic_year_id"] == year_id


def test_instructor_cannot_create_academic_year(client: TestClient, tmp_path) -> None:
    create_user(client, tmp_path / "test.sqlite3", "instructor")

    response = client.post(
        "/api/academic-years",
        json={
            "name": "2026-2027",
            "start_date": "2026-09-01",
            "end_date": "2027-06-30",
        },
    )

    assert response.status_code == 403


def test_term_dates_must_be_within_academic_year(client: TestClient, tmp_path) -> None:
    create_user(client, tmp_path / "test.sqlite3", "admin")
    year_response = client.post(
        "/api/academic-years",
        json={
            "name": "2026-2027",
            "start_date": "2026-09-01",
            "end_date": "2027-06-30",
        },
    )
    year_id = year_response.json()["id"]

    response = client.post(
        f"/api/academic-years/{year_id}/terms",
        json={
            "name": "Summer",
            "start_date": "2027-07-01",
            "end_date": "2027-08-01",
        },
    )

    assert response.status_code == 422
