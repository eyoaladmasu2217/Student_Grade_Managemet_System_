from contextlib import closing
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.security import hash_password

EMAIL = "teacher@example.edu"
PASSWORD = "Maple!River7Tunnel"
NEXT_PASSWORD = "Cobalt#Summit9Lantern"
THIRD_PASSWORD = "Quartz$Orchard4Beacon"


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "password.sqlite3")
    with TestClient(app) as test_client:
        with closing(sqlite3.connect(tmp_path / "password.sqlite3")) as connection:
            connection.execute(
                """
                INSERT INTO users (email, full_name, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (EMAIL, "Teacher", hash_password(PASSWORD), "instructor"),
            )
            connection.commit()
        assert test_client.post(
            "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ).status_code == 200
        yield test_client


def change(client: TestClient, current: str, new: str) -> int:
    return client.post(
        "/api/auth/change-password",
        json={"current_password": current, "new_password": new},
    ).status_code


def test_password_change_rechecks_the_hash_before_writing(client: TestClient) -> None:
    assert change(client, PASSWORD, NEXT_PASSWORD) == 200
    assert change(client, PASSWORD, THIRD_PASSWORD) == 400
    assert change(client, NEXT_PASSWORD, THIRD_PASSWORD) == 200
