import sqlite3
from contextlib import closing

import pytest

from app import database


@pytest.fixture
def db_path(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "pagination.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    database.initialize_database()
    with closing(sqlite3.connect(path)) as connection:
        connection.executemany(
            """
            INSERT INTO users (email, full_name, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            [
                (f"student{index}@example.edu", "Same Name", "hash", "student")
                for index in range(3)
            ],
        )
        connection.commit()
    return path


def test_user_pages_have_a_stable_order(db_path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        first = connection.execute(
            """
            SELECT id FROM users
            ORDER BY full_name, email, id
            LIMIT 1 OFFSET 1
            """
        ).fetchone()
        second = connection.execute(
            """
            SELECT id FROM users
            ORDER BY full_name, email, id
            LIMIT 1 OFFSET 1
            """
        ).fetchone()

    assert first == second
    assert first is not None


def test_user_ordering_uses_the_composite_index(db_path) -> None:
    with closing(sqlite3.connect(db_path)) as connection:
        plan = " ".join(
            " ".join(str(value) for value in row)
            for row in connection.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT id FROM users ORDER BY full_name, email, id LIMIT 10
                """
            )
        )

    assert "users_name_email_idx" in plan
