import logging
import os

logger = logging.getLogger("sgms.security")
DEFAULT_FRONTEND_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


class ConfigurationError(ValueError):
    """Raised when a security-sensitive environment value is unsafe."""


def environment() -> str:
    return (os.getenv("SGMS_ENV", "development").strip().lower() or "development")


def is_production() -> bool:
    return environment() in {"production", "prod"}


def use_secure_cookies() -> bool:
    explicitly_secure = os.getenv("SGMS_COOKIE_SECURE", "true").strip().lower() == "true"
    if explicitly_secure:
        return True
    if is_production():
        logger.warning("SGMS_COOKIE_SECURE=false is ignored in production")
        return True
    allow_insecure = os.getenv("SGMS_ALLOW_INSECURE_COOKIES", "false").strip().lower() == "true"
    return not allow_insecure


def frontend_origins() -> list[str]:
    raw = os.getenv("SGMS_FRONTEND_ORIGINS", ",".join(DEFAULT_FRONTEND_ORIGINS))
    origins: list[str] = []
    for entry in raw.split(","):
        origin = entry.strip().rstrip("/")
        if not origin:
            continue
        if "*" in origin:
            raise ConfigurationError(
                "SGMS_FRONTEND_ORIGINS must list explicit origins; wildcards are not allowed"
            )
        if not origin.startswith(("http://", "https://")):
            raise ConfigurationError(
                f"SGMS_FRONTEND_ORIGINS entries must be absolute HTTP(S) URLs: {origin}"
            )
        origins.append(origin)
    if not origins:
        raise ConfigurationError("SGMS_FRONTEND_ORIGINS must contain at least one origin")
    return origins
