from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.security import hash_password


@pytest.fixture
def db_path(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    database.initialize_database()
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
            ("student@example.edu", "Student", hash_password("a-secure-password"), "student"),
        )
        connection.commit()
    return path


def add_session(path, user_id: int, expires_at: datetime) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user_id, f"hash-{expires_at.isoformat()}", expires_at.isoformat()),
        )
        connection.commit()


def session_hashes(path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        return [row[0] for row in connection.execute("SELECT token_hash FROM sessions")]


def test_purge_removes_only_expired_sessions(db_path) -> None:
    add_session(db_path, 1, datetime.now(timezone.utc) - timedelta(hours=1))
    add_session(db_path, 1, datetime.now(timezone.utc) + timedelta(hours=1))

    removed = database.purge_expired_sessions()

    assert removed == 1
    assert len(session_hashes(db_path)) == 1


def test_startup_purges_expired_sessions(db_path) -> None:
    add_session(db_path, 1, datetime.now(timezone.utc) - timedelta(days=1))
    add_session(db_path, 1, datetime.now(timezone.utc) + timedelta(hours=1))

    with TestClient(app):
        pass

    assert len(session_hashes(db_path)) == 1
