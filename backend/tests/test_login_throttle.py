from contextlib import closing
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from app import database
from app.login_guard import (
    MAX_FAILURES_PER_ACCOUNT,
    MAX_FAILURES_PER_ADDRESS,
    WINDOW_SECONDS,
    LoginThrottle,
    login_throttle,
)
from app.main import app
from app.security import hash_password

EMAIL = "learner@example.edu"
PASSWORD = "a-secure-password"


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    login_throttle.reset()
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.sqlite3")
    with TestClient(app) as test_client:
        with closing(sqlite3.connect(tmp_path / "test.sqlite3")) as connection:
            connection.execute(
                "INSERT INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
                (EMAIL, "Learner", hash_password(PASSWORD), "student"),
            )
            connection.commit()
        yield test_client
    login_throttle.reset()


def attempt(client: TestClient, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_expired_throttle_keys_are_swept() -> None:
    guard = LoginThrottle()
    old = time.monotonic() - WINDOW_SECONDS - 1
    guard._accounts[("old@example.edu", "old-address")] = [old]
    guard._addresses["old-address"] = [old]
    guard._last_sweep = 0.0

    guard.retry_after("new@example.edu", "new-address")

    assert ("old@example.edu", "old-address") not in guard._accounts
    assert "old-address" not in guard._addresses


def test_recent_throttle_keys_survive_a_sweep() -> None:
    guard = LoginThrottle()
    guard.record_failure("active@example.edu", "active-address")
    guard._last_sweep = 0.0

    guard.retry_after("active@example.edu", "active-address")

    assert ("active@example.edu", "active-address") in guard._accounts
    assert "active-address" in guard._addresses


def test_repeated_failures_lock_the_account(client: TestClient) -> None:
    for _ in range(MAX_FAILURES_PER_ACCOUNT):
        assert attempt(client, EMAIL, "wrong-password").status_code == 401

    blocked = attempt(client, EMAIL, "wrong-password")
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1

    assert attempt(client, EMAIL, PASSWORD).status_code == 429


def test_correct_credentials_clear_the_failure_count(client: TestClient) -> None:
    for _ in range(MAX_FAILURES_PER_ACCOUNT - 1):
        attempt(client, EMAIL, "wrong-password")

    assert attempt(client, EMAIL, PASSWORD).status_code == 200
    for _ in range(MAX_FAILURES_PER_ACCOUNT - 1):
        assert attempt(client, EMAIL, "wrong-password").status_code == 401
    assert attempt(client, EMAIL, PASSWORD).status_code == 200


def test_address_wide_attempts_are_limited(client: TestClient) -> None:
    for index in range(MAX_FAILURES_PER_ADDRESS):
        response = attempt(client, f"unknown{index}@example.edu", "wrong-password")
        assert response.status_code == 401

    assert attempt(client, "fresh@example.edu", "wrong-password").status_code == 429
