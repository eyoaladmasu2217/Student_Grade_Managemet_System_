from pathlib import Path

import pytest

from app import database


def test_connect_restricts_file_and_directory_permissions(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "nested" / "test.sqlite3"
    monkeypatch.setattr(database, "DATABASE_PATH", path)
    calls: list[tuple[Path, int]] = []
    monkeypatch.setattr(
        database.os,
        "chmod",
        lambda target, mode: calls.append((Path(target), mode)),
    )

    connection = database.connect()
    connection.close()

    assert (path.parent, 0o700) in calls
    assert (path, 0o600) in calls


def test_permission_errors_do_not_prevent_connecting(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.sqlite3")

    def deny(*_: object) -> None:
        raise OSError("access denied")

    monkeypatch.setattr(database.os, "chmod", deny)

    connection = database.connect()
    connection.close()

    assert (tmp_path / "test.sqlite3").exists()
