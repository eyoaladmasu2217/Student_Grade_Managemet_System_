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


def test_admin_can_create_course_section(client: TestClient, tmp_path) -> None:
    create_user(client, tmp_path / "test.sqlite3", "admin")
    with sqlite3.connect(tmp_path / "test.sqlite3") as connection:
        connection.execute(
            "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
            ("instructor@example.edu", "Course Instructor", hash_password("a-secure-password"), "instructor"),
        )
        instructor_id = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            ("instructor@example.edu",),
        ).fetchone()[0]

    year_response = client.post(
        "/api/academic-years",
        json={
            "name": "2026-2027",
            "start_date": "2026-09-01",
            "end_date": "2027-06-30",
        },
    )
    term_response = client.post(
        f"/api/academic-years/{year_response.json()['id']}/terms",
        json={
            "name": "Fall",
            "start_date": "2026-09-01",
            "end_date": "2026-12-20",
        },
    )
    course_response = client.post(
        "/api/courses",
        json={"code": "cs101", "title": "Introduction to Computing"},
    )

    assert course_response.status_code == 201
    assert course_response.json()["code"] == "CS101"
    section_response = client.post(
        f"/api/courses/{course_response.json()['id']}/sections",
        json={
            "term_id": term_response.json()["id"],
            "instructor_id": instructor_id,
            "section_code": "a",
        },
    )

    assert section_response.status_code == 201
    assert section_response.json()["section_code"] == "A"
    assert section_response.json()["instructor_name"] == "Course Instructor"


def test_instructor_only_lists_assigned_sections(client: TestClient, tmp_path) -> None:
    create_user(client, tmp_path / "test.sqlite3", "instructor")
    response = client.get("/api/sections")

    assert response.status_code == 200
    assert response.json() == []


def test_admin_can_create_user_without_exposing_password_hash(
    client: TestClient,
    tmp_path,
) -> None:
    create_user(client, tmp_path / "test.sqlite3", "admin")

    response = client.post(
        "/api/users",
        json={
            "email": "new.student@example.edu",
            "full_name": "New Student",
            "password": "a-secure-password",
            "role": "student",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "new.student@example.edu"
    assert "password_hash" not in response.json()


def test_student_cannot_list_users(client: TestClient, tmp_path) -> None:
    create_user(client, tmp_path / "test.sqlite3", "student")

    response = client.get("/api/users")

    assert response.status_code == 403


def test_student_only_sees_sections_they_are_enrolled_in(
    client: TestClient,
    tmp_path,
) -> None:
    create_user(client, tmp_path / "test.sqlite3", "admin")
    instructor_response = client.post(
        "/api/users",
        json={
            "email": "instructor@example.edu",
            "full_name": "Course Instructor",
            "password": "a-secure-password",
            "role": "instructor",
        },
    )
    student_response = client.post(
        "/api/users",
        json={
            "email": "student@example.edu",
            "full_name": "Student One",
            "password": "a-secure-password",
            "role": "student",
        },
    )
    year_response = client.post(
        "/api/academic-years",
        json={
            "name": "2026-2027",
            "start_date": "2026-09-01",
            "end_date": "2027-06-30",
        },
    )
    term_response = client.post(
        f"/api/academic-years/{year_response.json()['id']}/terms",
        json={
            "name": "Fall",
            "start_date": "2026-09-01",
            "end_date": "2026-12-20",
        },
    )
    course_response = client.post(
        "/api/courses",
        json={"code": "CS101", "title": "Introduction to Computing"},
    )
    section_response = client.post(
        f"/api/courses/{course_response.json()['id']}/sections",
        json={
            "term_id": term_response.json()["id"],
            "instructor_id": instructor_response.json()["id"],
            "section_code": "A",
        },
    )
    other_section_response = client.post(
        f"/api/courses/{course_response.json()['id']}/sections",
        json={
            "term_id": term_response.json()["id"],
            "instructor_id": instructor_response.json()["id"],
            "section_code": "B",
        },
    )
    assert other_section_response.status_code == 201
    enrollment_response = client.post(
        f"/api/sections/{section_response.json()['id']}/enrollments",
        json={"student_id": student_response.json()["id"]},
    )
    assert enrollment_response.status_code == 201

    client.post(
        "/api/auth/login",
        json={"email": "student@example.edu", "password": "a-secure-password"},
    )
    sections_response = client.get("/api/sections")
    mine_response = client.get("/api/enrollments/mine")

    assert sections_response.status_code == 200
    assert [section["id"] for section in sections_response.json()] == [
        section_response.json()["id"]
    ]
    assert mine_response.status_code == 200
    assert [section["id"] for section in mine_response.json()] == [
        section_response.json()["id"]
    ]
