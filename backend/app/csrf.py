import logging

from fastapi import Request, Response, status
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.audit import log_security_event
from app.config import frontend_origins

logger = logging.getLogger("sgms.security")
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
REJECTED_FETCH_SITES = frozenset({"cross-site", "same-site"})


def _allowed_origins(request: Request) -> frozenset[str]:
    configured = getattr(request.app.state, "allowed_origins", None)
    if configured is None:
        return frozenset(frontend_origins())
    return configured


def _rejected(request: Request, detail: str) -> JSONResponse:
    address = request.client.host if request.client else "unknown"
    logger.warning("Blocked unsafe request: %s", detail)
    log_security_event(
        "csrf",
        "failure",
        reason=detail,
        path=request.url.path,
        method=request.method,
        address=address,
    )
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": detail},
    )


async def validate_request_origin(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    if request.method not in UNSAFE_METHODS:
        return await call_next(request)

    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site")
    if origin is None and fetch_site is None:
        return await call_next(request)

    if origin is not None and origin.rstrip("/") not in _allowed_origins(request):
        return _rejected(request,"Request origin is not allowed")

    if (origin is not None or fetch_site is not None) and request.headers.get(
        "x-requested-with"
    ) != "XMLHttpRequest":
        return _rejected(request,"Browser state changes require a custom request header")

    if fetch_site in REJECTED_FETCH_SITES:
        return _rejected(request,"Cross-site state changes are not allowed")

    return await call_next(request)
