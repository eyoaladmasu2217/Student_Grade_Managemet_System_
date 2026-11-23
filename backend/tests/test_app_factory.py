import pytest

from app.main import create_app


def test_documentation_is_available_outside_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SGMS_ENV", "development")

    paths = {getattr(route, "path", None) for route in create_app().routes}

    assert {"/docs", "/redoc", "/openapi.json"} <= paths


@pytest.mark.parametrize("environment", ["production", "prod"])
def test_documentation_is_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("SGMS_ENV", environment)

    paths = {getattr(route, "path", None) for route in create_app().routes}

    assert paths.isdisjoint({"/docs", "/redoc", "/openapi.json"})
    assert "/api/health" in paths
