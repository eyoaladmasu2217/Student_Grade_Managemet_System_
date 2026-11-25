from contextlib import closing

import pytest

from app import database
from app.grade_scale import letter_grade_for, letter_grade_from, load_grade_bands


@pytest.fixture
def db_path(tmp_path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "grade-scale.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    database.initialize_database()
    return path


def test_in_memory_lookup_matches_database_lookup(db_path) -> None:
    with closing(database.connect()) as connection:
        bands = load_grade_bands(connection)
        for percentage in (None, 0, 59.99, 60, 79.9, 80, 89.99, 90, 100):
            assert letter_grade_from(bands, percentage) == letter_grade_for(
                connection, percentage
            )


def test_bands_are_loaded_with_one_query(db_path) -> None:
    queries: list[str] = []
    with closing(database.connect()) as connection:
        connection.set_trace_callback(queries.append)
        load_grade_bands(connection)

    assert len([query for query in queries if "grade_bands" in query]) == 1
