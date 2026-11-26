from contextlib import closing
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app import corrections as corrections_module
from app import scores as scores_module
from app.main import app
from app.security import hash_password

PASSWORD = "a-secure-password"


@pytest.fixture
def gradebook_setup(tmp_path, monkeypatch: pytest.MonkeyPatch):
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
                "INSERT INTO terms (academic_year_id, name, start_date, end_date) VALUES (?, ?, ?, ?)",
                (year_id, "Fall", "2026-09-01", "2026-12-20"),
            )
            term_id = connection.execute("SELECT id FROM terms").fetchone()[0]
            connection.execute("INSERT INTO courses (code, title) VALUES (?, ?)", ("CS101", "Computing"))
            course_id = connection.execute("SELECT id FROM courses").fetchone()[0]
            connection.execute(
                "INSERT INTO sections (course_id, term_id, instructor_id, section_code) VALUES (?, ?, ?, ?)",
                (course_id, term_id, instructor_id, "A"),
            )
            section_id = connection.execute("SELECT id FROM sections").fetchone()[0]
            connection.execute(
                "INSERT INTO enrollments (section_id, student_id, status) VALUES (?, ?, 'active')",
                (section_id, student_id),
            )
            connection.execute(
                "INSERT INTO assessment_categories (section_id, name, weight) VALUES (?, ?, ?)",
                (section_id, "Exams", 100),
            )
            category_id = connection.execute("SELECT id FROM assessment_categories").fetchone()[0]
            connection.execute(
                "INSERT INTO assessments (category_id, title, max_points) VALUES (?, ?, ?)",
                (category_id, "Final", 100),
            )
            assessment_id = connection.execute("SELECT id FROM assessments").fetchone()[0]
            connection.execute(
                "INSERT INTO assessment_scores (assessment_id, student_id, points, updated_by) VALUES (?, ?, ?, ?)",
                (assessment_id, student_id, 90, instructor_id),
            )
            connection.execute(
                "INSERT INTO section_releases (section_id, released_by) VALUES (?, ?)",
                (section_id, instructor_id),
            )
            connection.execute(
                "INSERT INTO released_grades (section_id, student_id, percentage, letter_grade) VALUES (?, ?, ?, ?)",
                (section_id, student_id, 90, "A"),
            )
            connection.commit()
        assert client.post(
            "/api/auth/login",
            json={"email": "instructor@example.edu", "password": PASSWORD},
        ).status_code == 200
        yield client, assessment_id, student_id


def test_score_authorization_runs_inside_write_transaction(
    gradebook_setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, assessment_id, student_id = gradebook_setup
    observed: list[bool] = []
    original = scores_module.require_category_manager

    def recording_guard(connection, category_id, user):
        observed.append(connection.in_transaction)
        return original(connection, category_id, user)

    monkeypatch.setattr(scores_module, "require_category_manager", recording_guard)

    response = client.put(
        f"/api/assessments/{assessment_id}/scores/{student_id}",
        json={"points": 91},
    )

    assert response.status_code == 409
    assert observed == [True]


def test_correction_authorization_runs_inside_write_transaction(
    gradebook_setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, assessment_id, student_id = gradebook_setup
    observed: list[bool] = []
    original = corrections_module.require_section_manager

    def recording_guard(connection, section_id, user):
        observed.append(connection.in_transaction)
        return original(connection, section_id, user)

    monkeypatch.setattr(corrections_module, "require_section_manager", recording_guard)

    response = client.put(
        f"/api/assessments/{assessment_id}/scores/{student_id}/correction",
        json={
            "points": 80,
            "reason_code": "grading_error",
            "reason": "Correcting the recorded score",
        },
    )

    assert response.status_code == 200
    assert observed == [True]
