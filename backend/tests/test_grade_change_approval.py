import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.security import hash_password

PASSWORD = "a-secure-password"


@pytest.fixture
def released_section(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    with TestClient(app) as client:
        with closing(sqlite3.connect(path)) as connection:
            connection.executemany(
                "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
                [
                    ("admin@example.edu", "Administrator", hash_password(PASSWORD), "admin"),
                    ("instructor@example.edu", "Instructor", hash_password(PASSWORD), "instructor"),
                    ("student@example.edu", "Student", hash_password(PASSWORD), "student"),
                ],
            )
            admin_id = connection.execute(
                "SELECT id FROM users WHERE email = 'admin@example.edu'"
            ).fetchone()[0]
            instructor_id = connection.execute(
                "SELECT id FROM users WHERE email = 'instructor@example.edu'"
            ).fetchone()[0]
            student_id = connection.execute(
                "SELECT id FROM users WHERE email = 'student@example.edu'"
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
                (section_id, "Exams", 100),
            )
            category_id = connection.execute(
                "SELECT id FROM assessment_categories"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO assessments (category_id, title, max_points) VALUES (?, ?, ?)",
                (category_id, "Final", 100),
            )
            assessment_id = connection.execute("SELECT id FROM assessments").fetchone()[0]
            connection.execute(
                """
                INSERT INTO assessment_scores (assessment_id, student_id, points, updated_by)
                VALUES (?, ?, ?, ?)
                """,
                (assessment_id, student_id, 92, instructor_id),
            )
            connection.execute(
                "INSERT INTO section_releases (section_id, released_by) VALUES (?, ?)",
                (section_id, instructor_id),
            )
            connection.execute(
                """
                INSERT INTO released_grades (section_id, student_id, percentage, letter_grade)
                VALUES (?, ?, ?, ?)
                """,
                (section_id, student_id, 92, "A"),
            )
            connection.commit()
        yield client, path, section_id, assessment_id, student_id, admin_id, instructor_id


def login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200


def request_change(client: TestClient, assessment_id: int, student_id: int) -> dict:
    response = client.put(
        f"/api/assessments/{assessment_id}/scores/{student_id}/correction",
        json={
            "points": 80,
            "reason_code": "misgraded_work",
            "reason": "The final exam was scored with the wrong key",
        },
    )
    assert response.status_code == 200
    return response.json()


def stored_score(path, assessment_id: int, student_id: int) -> float:
    with closing(sqlite3.connect(path)) as connection:
        return connection.execute(
            """
            SELECT points FROM assessment_scores
            WHERE assessment_id = ? AND student_id = ?
            """,
            (assessment_id, student_id),
        ).fetchone()[0]


def test_instructor_request_stays_pending_until_approved(released_section) -> None:
    client, path, section_id, assessment_id, student_id, admin_id, _ = released_section
    login(client, "instructor@example.edu")
    request = request_change(client, assessment_id, student_id)

    assert request["status"] == "pending"
    assert request["reason_code"] == "misgraded_work"
    assert request["requested_by_name"] == "Instructor"
    assert request["reviewed_by"] is None
    assert request["new_percentage"] == 80
    assert stored_score(path, assessment_id, student_id) == 92

    login(client, "instructor@example.edu")
    queue = client.get("/api/grade-change-requests")
    assert queue.status_code == 403

    login(client, "admin@example.edu")
    queue = client.get("/api/grade-change-requests?status=pending")
    assert queue.status_code == 200
    assert [entry["id"] for entry in queue.json()] == [request["id"]]
    trail = client.get(f"/api/sections/{section_id}/audit-trail")
    assert [event["event"] for event in trail.json()] == ["requested"]

    approved = client.post(
        f"/api/grade-change-requests/{request['id']}/approve",
        json={"note": "Verified the answer key with the department"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewed_by"] == admin_id
    assert approved.json()["reviewed_by_name"] == "Administrator"
    assert stored_score(path, assessment_id, student_id) == 80

    login(client, "student@example.edu")
    grade = client.get(f"/api/sections/{section_id}/my-grade")
    assert grade.json()["percentage"] == 80
    assert grade.json()["letter_grade"] == "B"

    login(client, "admin@example.edu")
    assert client.get("/api/grade-change-requests?status=pending").json() == []
    trail = client.get(f"/api/sections/{section_id}/audit-trail")
    assert [event["event"] for event in trail.json()] == ["approved", "requested"]


def test_rejected_request_does_not_change_the_grade(released_section) -> None:
    client, path, _, assessment_id, student_id, admin_id, _ = released_section
    login(client, "instructor@example.edu")
    request = request_change(client, assessment_id, student_id)

    login(client, "admin@example.edu")
    rejected = client.post(
        f"/api/grade-change-requests/{request['id']}/reject",
        json={"note": "The original grading key was correct"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["reviewed_by"] == admin_id
    assert rejected.json()["review_note"] == "The original grading key was correct"
    assert stored_score(path, assessment_id, student_id) == 92

    again = client.post(
        f"/api/grade-change-requests/{request['id']}/approve",
        json={"note": "Trying to approve after rejection"},
    )
    assert again.status_code == 409


def test_only_admins_can_review_grade_changes(released_section) -> None:
    client, _, _, assessment_id, student_id, _, _ = released_section
    login(client, "instructor@example.edu")
    request = request_change(client, assessment_id, student_id)

    assert (
        client.post(
            f"/api/grade-change-requests/{request['id']}/approve", json={"note": ""}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/grade-change-requests/{request['id']}/reject",
            json={"note": "Rejected by the instructor"},
        ).status_code
        == 403
    )


def test_reason_code_is_required(released_section) -> None:
    client, _, _, assessment_id, student_id, _, _ = released_section
    login(client, "instructor@example.edu")

    response = client.put(
        f"/api/assessments/{assessment_id}/scores/{student_id}/correction",
        json={"points": 80, "reason": "A reason without a controlled code"},
    )
    assert response.status_code == 422

    response = client.put(
        f"/api/assessments/{assessment_id}/scores/{student_id}/correction",
        json={
            "points": 80,
            "reason_code": "unknown_code",
            "reason": "A reason with an unknown code",
        },
    )
    assert response.status_code == 422


def test_rejection_requires_an_explanation(released_section) -> None:
    client, _, _, assessment_id, student_id, _, _ = released_section
    login(client, "instructor@example.edu")
    request = request_change(client, assessment_id, student_id)

    login(client, "admin@example.edu")
    response = client.post(
        f"/api/grade-change-requests/{request['id']}/reject",
        json={"note": "no"},
    )
    assert response.status_code == 422
