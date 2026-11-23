from app import security
from app.security import dummy_password_hash, hash_password, verify_login_password, verify_password


def test_unknown_account_runs_the_same_verification_work(monkeypatch) -> None:
    calls: list[str] = []
    original = security.verify_password

    def recording_verify(password: str, stored_hash: str) -> bool:
        calls.append(stored_hash)
        return original(password, stored_hash)

    monkeypatch.setattr(security, "verify_password", recording_verify)

    assert verify_login_password("any-password", None) is False
    assert calls == [dummy_password_hash()]


def test_known_account_uses_its_stored_hash(monkeypatch) -> None:
    stored = hash_password("a-secure-password")
    calls: list[str] = []
    original = security.verify_password

    def recording_verify(password: str, password_hash: str) -> bool:
        calls.append(password_hash)
        return original(password, password_hash)

    monkeypatch.setattr(security, "verify_password", recording_verify)

    assert verify_login_password("a-secure-password", stored) is True
    assert calls == [stored]


def test_dummy_hash_never_matches_a_real_password() -> None:
    assert verify_password("a-secure-password", dummy_password_hash()) is False
