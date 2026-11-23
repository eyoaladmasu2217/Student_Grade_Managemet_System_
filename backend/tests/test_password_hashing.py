import base64

import pytest

from app.security import hash_password, verify_password


def test_valid_hash_still_verifies() -> None:
    stored = hash_password("a-secure-password")

    assert verify_password("a-secure-password", stored) is True
    assert verify_password("a-wrong-password", stored) is False


@pytest.mark.parametrize(
    "stored",
    [
        "",
        "not-a-hash",
        "scrypt$16384$only$three",
        "scrypt$16384$!!!$$",
        "scrypt$999999$c2FsdA$c2FsdA",
        "bcrypt$16384$c2FsdA$c2FsdA",
    ],
)
def test_malformed_hashes_fail_closed(stored: str) -> None:
    assert verify_password("a-secure-password", stored) is False


def test_oversized_derived_key_is_rejected_before_allocation() -> None:
    salt = base64.urlsafe_b64encode(b"x" * 16).decode("ascii")
    huge_key = base64.urlsafe_b64encode(b"x" * 100_000).decode("ascii")

    assert verify_password("a-secure-password", f"scrypt$16384${salt}${huge_key}") is False
