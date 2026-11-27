import sqlite3
from contextlib import closing

import pytest

from app import database


@pytest.fixture
def db_path(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    database.initialize_database()
    return path


def test_audit_event_triggers_exist(db_path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            )
        }

    assert "grade_change_events_no_update" in names
    assert "grade_change_events_no_delete" in names


def test_audit_events_cannot_be_edited_or_deleted(db_path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO grade_change_events
                (correction_id, section_id, event, actor_id, note, occurred_at)
            VALUES (1, 1, 'requested', 1, 'original', '2026-01-01T00:00:00+00:00')
            """
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE grade_change_events SET note = 'rewritten' WHERE id = 1"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM grade_change_events WHERE id = 1")

        note = connection.execute(
            "SELECT note FROM grade_change_events WHERE id = 1"
        ).fetchone()[0]
    assert note == "original"
