from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.security import hash_password

DB_NAME = "test.sqlite3"
EMAIL = "student@example.edu"
PASSWORD = "a-secure-password"


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / DB_NAME)
    with TestClient(app) as test_client:
        with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection:
            connection.execute(
                "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
                (EMAIL, "Student", hash_password(PASSWORD), "student"),
            )
            connection.commit()
        response = test_client.post(
            "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )
        assert response.status_code == 200
        yield test_client


def set_session_time(db_path, column: str, when: datetime) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(f"UPDATE sessions SET {column} = ?", (when.isoformat(),))
        connection.commit()


def session_count(db_path) -> int:
    with closing(sqlite3.connect(db_path)) as connection:
        return connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]


def test_idle_sessions_are_revoked(client: TestClient, tmp_path) -> None:
    set_session_time(
        tmp_path / DB_NAME,
        "last_seen_at",
        datetime.now(timezone.utc) - timedelta(hours=3),
    )

    assert client.get("/api/auth/me").status_code == 401
    assert session_count(tmp_path / DB_NAME) == 0


def test_activity_refreshes_the_idle_window(client: TestClient, tmp_path) -> None:
    old = datetime.now(timezone.utc) - timedelta(hours=1)
    set_session_time(tmp_path / DB_NAME, "last_seen_at", old)

    assert client.get("/api/auth/me").status_code == 200
    with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection:
        current = connection.execute("SELECT last_seen_at FROM sessions").fetchone()[0]
    assert datetime.fromisoformat(current.replace("Z", "+00:00")) > old


def test_absolute_expiry_is_still_enforced(client: TestClient, tmp_path) -> None:
    set_session_time(
        tmp_path / DB_NAME,
        "expires_at",
        datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    assert client.get("/api/auth/me").status_code == 401
    assert session_count(tmp_path / DB_NAME) == 0


def test_legacy_sessions_tables_are_migrated(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()

    database.initialize_database()

    with closing(sqlite3.connect(db_path)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(sessions)")}
    assert "last_seen_at" in columns
