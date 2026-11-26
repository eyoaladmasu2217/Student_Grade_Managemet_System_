import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.security import hash_password

PASSWORD = "a-secure-password"


@pytest.fixture
def simulation_setup(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    with TestClient(app) as client:
        with closing(sqlite3.connect(path)) as connection:
            connection.executemany(
                "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
                [
                    ("instructor@example.edu", "Instructor", hash_password(PASSWORD), "instructor"),
                    ("student@example.edu", "Student", hash_password(PASSWORD), "student"),
                    ("other@example.edu", "Other student", hash_password(PASSWORD), "student"),
                ],
            )
            instructor_id = connection.execute(
                "SELECT id FROM users WHERE email = ?", ("instructor@example.edu",)
            ).fetchone()[0]
            student_id = connection.execute(
                "SELECT id FROM users WHERE email = ?", ("student@example.edu",)
            ).fetchone()[0]

            connection.execute(
                "INSERT INTO academic_years (name, start_date, end_date) VALUES (?, ?, ?)",
                ("2026-2027", "2026-09-01", "2027-06-30"),
            )
            year_id = connection.execute("SELECT id FROM academic_years").fetchone()[0]
            connection.execute(
                """
                INSERT INTO terms (academic_year_id, name, start_date, end_date)
                VALUES (?, ?, ?, ?)
                """,
                (year_id, "Fall", "2026-09-01", "2026-12-20"),
            )
            term_id = connection.execute("SELECT id FROM terms").fetchone()[0]
            connection.execute("INSERT INTO courses (code, title) VALUES (?, ?)", ("CS101", "Computing"))
            course_id = connection.execute("SELECT id FROM courses").fetchone()[0]
            connection.execute(
                """
                INSERT INTO sections (course_id, term_id, instructor_id, section_code)
                VALUES (?, ?, ?, ?)
                """,
                (course_id, term_id, instructor_id, "A"),
            )
            section_id = connection.execute("SELECT id FROM sections").fetchone()[0]
            connection.execute(
                "INSERT INTO enrollments (section_id, student_id) VALUES (?, ?)",
                (section_id, student_id),
            )
            connection.execute(
                "INSERT INTO assessment_categories (section_id, name, weight) VALUES (?, ?, ?)",
                (section_id, "Exams", 60),
            )
            category_id = connection.execute(
                "SELECT id FROM assessment_categories"
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO assessments (category_id, title, max_points, due_date)
                VALUES (?, ?, ?, ?)
                """,
                (category_id, "Midterm", 40, "2026-10-01"),
            )
            assessment_id = connection.execute("SELECT id FROM assessments").fetchone()[0]
            connection.execute(
                """
                INSERT INTO assessment_scores (assessment_id, student_id, points, updated_by)
                VALUES (?, ?, ?, ?)
                """,
                (assessment_id, student_id, 32, instructor_id),
            )
            connection.commit()
        yield client, path, section_id, assessment_id


def login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200


def test_simulation_shows_structure_but_hides_unreleased_scores(
    simulation_setup,
) -> None:
    client, _, section_id, _ = simulation_setup
    login(client, "student@example.edu")

    response = client.get(f"/api/sections/{section_id}/what-if")

    assert response.status_code == 200
    body = response.json()
    assert body["course_code"] == "CS101"
    assert body["grades_released"] is False
    assert body["categories"] == [{"id": 1, "name": "Exams", "weight": 60}]
    assert body["assessments"][0]["max_points"] == 40
    assert body["assessments"][0]["points"] is None
    assert {band["code"] for band in body["grade_bands"]} == {"A", "B", "C", "D", "F"}


def test_simulation_reveals_scores_after_grade_release(simulation_setup) -> None:
    client, path, section_id, assessment_id = simulation_setup
    login(client, "student@example.edu")
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "INSERT INTO section_releases (section_id, released_by) VALUES (?, ?)",
            (section_id, 1),
        )
        connection.commit()

    response = client.get(f"/api/sections/{section_id}/what-if")

    assert response.status_code == 200
    assert response.json()["grades_released"] is True
    assert response.json()["assessments"][0]["points"] == 32
    assert response.json()["assessments"][0]["id"] == assessment_id


def test_simulation_requires_active_enrollment(simulation_setup) -> None:
    client, _, section_id, _ = simulation_setup
    login(client, "other@example.edu")

    response = client.get(f"/api/sections/{section_id}/what-if")

    assert response.status_code == 404


def test_simulation_is_student_only(simulation_setup) -> None:
    client, _, section_id, _ = simulation_setup
    login(client, "instructor@example.edu")

    response = client.get(f"/api/sections/{section_id}/what-if")

    assert response.status_code == 403
