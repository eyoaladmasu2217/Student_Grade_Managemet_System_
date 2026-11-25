from contextlib import closing

import pytest

from app import database
from app.grade_math import calculate_grade_for_student, calculate_grades_for_students


@pytest.fixture
def db_path(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "batch-grades.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    database.initialize_database()
    with closing(database.connect()) as connection:
        connection.executemany(
            """
            INSERT INTO users (id, email, full_name, password_hash, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "teacher@example.edu", "Teacher", "hash", "instructor"),
                (2, "a@example.edu", "Student A", "hash", "student"),
                (3, "b@example.edu", "Student B", "hash", "student"),
                (4, "c@example.edu", "Student C", "hash", "student"),
            ],
        )
        connection.execute(
            """
            INSERT INTO academic_years (id, name, start_date, end_date)
            VALUES (1, '2026', '2026-01-01', '2026-12-31')
            """
        )
        connection.execute(
            """
            INSERT INTO terms (id, academic_year_id, name, start_date, end_date)
            VALUES (1, 1, 'Term 1', '2026-01-01', '2026-06-30')
            """
        )
        connection.execute(
            "INSERT INTO courses (id, code, title) VALUES (1, 'CS101', 'Intro')"
        )
        connection.execute(
            """
            INSERT INTO sections (id, course_id, term_id, instructor_id, section_code)
            VALUES (1, 1, 1, 1, 'A')
            """
        )
        connection.executemany(
            "INSERT INTO enrollments (section_id, student_id) VALUES (1, ?)",
            [(2,), (3,), (4,)],
        )
        connection.executemany(
            """
            INSERT INTO assessment_categories (id, section_id, name, weight)
            VALUES (?, 1, ?, ?)
            """,
            [(1, "Exams", 60), (2, "Homework", 40)],
        )
        connection.executemany(
            """
            INSERT INTO assessments (id, category_id, title, max_points)
            VALUES (?, ?, ?, ?)
            """,
            [(1, 1, "Midterm", 100), (2, 1, "Final", 100), (3, 2, "HW1", 20), (4, 2, "HW2", 20)],
        )
        connection.executemany(
            """
            INSERT INTO assessment_scores (assessment_id, student_id, points, updated_by)
            VALUES (?, ?, ?, 1)
            """,
            [(1, 2, 90), (2, 2, 80), (3, 2, 20), (1, 3, 70), (3, 3, 10)],
        )
        connection.commit()
    return path


def test_batch_summaries_match_single_student_summaries(db_path) -> None:
    with closing(database.connect()) as connection:
        batch = calculate_grades_for_students(connection, 1, [2, 3, 4])
        for student_id in (2, 3, 4):
            assert batch[student_id] == calculate_grade_for_student(connection, 1, student_id)


def test_batch_summaries_use_one_query(db_path) -> None:
    queries: list[str] = []
    with closing(database.connect()) as connection:
        connection.set_trace_callback(queries.append)
        result = calculate_grades_for_students(connection, 1, [2, 3, 4])

    assert len(result) == 3
    assert len(queries) == 1


def test_batch_summaries_handle_an_empty_student_list(db_path) -> None:
    with closing(database.connect()) as connection:
        assert calculate_grades_for_students(connection, 1, []) == {}
