import pytest

from app.config import (
    DEFAULT_FRONTEND_ORIGINS,
    ConfigurationError,
    environment,
    frontend_origins,
    is_production,
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
