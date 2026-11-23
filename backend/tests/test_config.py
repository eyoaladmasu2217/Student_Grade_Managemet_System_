import pytest
from fastapi import Response

from app.auth import set_session_cookie
from app.config import (
    DEFAULT_FRONTEND_ORIGINS,
    ConfigurationError,
    environment,
    frontend_origins,
    is_production,
    use_secure_cookies,
)


def test_default_origins_are_localhost_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SGMS_FRONTEND_ORIGINS", raising=False)

    assert frontend_origins() == list(DEFAULT_FRONTEND_ORIGINS)


def test_origins_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "SGMS_FRONTEND_ORIGINS", " https://grades.example.edu/ , ,http://localhost:5173"
    )

    assert frontend_origins() == [
        "https://grades.example.edu",
        "http://localhost:5173",
    ]


@pytest.mark.parametrize("value", ["*", "https://*.example.edu", "grades.example.edu", ""])
def test_unsafe_or_empty_origins_are_rejected(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("SGMS_FRONTEND_ORIGINS", value)

    with pytest.raises(ConfigurationError):
        frontend_origins()


def test_cookies_are_secure_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SGMS_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("SGMS_ALLOW_INSECURE_COOKIES", raising=False)
    monkeypatch.delenv("SGMS_ENV", raising=False)

    assert use_secure_cookies() is True


def test_insecure_cookies_require_an_explicit_development_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ENV", "development")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")

    assert use_secure_cookies() is False


def test_production_can_never_disable_secure_cookies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    monkeypatch.setenv("SGMS_ALLOW_INSECURE_COOKIES", "true")
    monkeypatch.setenv("SGMS_ENV", "production")

    assert use_secure_cookies() is True


def test_production_session_cookie_always_has_secure_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SGMS_ENV", "production")
    monkeypatch.setenv("SGMS_COOKIE_SECURE", "false")
    response = Response()

    set_session_cookie(response, "sample-token")

    assert "secure" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize(
    ("value", "expected_environment", "expected_production"),
    [
        ("production", "production", True),
        ("PROD", "prod", True),
        ("", "development", False),
    ],
)
def test_environment_detection(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    expected_environment: str,
    expected_production: bool,
) -> None:
    monkeypatch.setenv("SGMS_ENV", value)

    assert environment() == expected_environment
    assert is_production() is expected_production
