import sqlite3
from contextlib import closing

import pytest

from app import database


def test_legacy_corrections_table_is_migrated(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            """
            CREATE TABLE grade_corrections (
                id INTEGER PRIMARY KEY,
                section_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                assessment_id INTEGER NOT NULL,
                previous_points REAL NOT NULL,
                new_points REAL NOT NULL,
                previous_percentage REAL NOT NULL,
                new_percentage REAL NOT NULL,
                previous_letter_grade TEXT NOT NULL,
                new_letter_grade TEXT NOT NULL,
                changed_by INTEGER NOT NULL,
                reason TEXT NOT NULL,
                changed_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO grade_corrections (
                section_id, student_id, assessment_id, previous_points, new_points,
                previous_percentage, new_percentage, previous_letter_grade,
                new_letter_grade, changed_by, reason, changed_at
            ) VALUES (1, 2, 3, 90, 80, 90, 80, 'A', 'B', 4, 'Legacy correction', '2026-01-01')
            """
        )
        connection.commit()

    database.initialize_database()

    with closing(sqlite3.connect(path)) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(grade_corrections)")
        }
        assert {
            "reason_code",
            "status",
            "requested_by",
            "reviewed_by",
            "reviewed_at",
            "review_note",
        } <= columns
        row = connection.execute(
            """
            SELECT reason_code, status FROM grade_corrections WHERE id = 1
            """
        ).fetchone()
        assert row == ("other", "approved")
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'grade_change_events'"
        ).fetchone()
