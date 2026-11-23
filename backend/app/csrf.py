import logging

from fastapi import Request, Response, status
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.config import frontend_origins

logger = logging.getLogger("sgms.security")
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
REJECTED_FETCH_SITES = frozenset({"cross-site", "same-site"})


def _rejected(detail: str) -> JSONResponse:
    logger.warning("Blocked unsafe request: %s", detail)
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

    if origin is not None and origin.rstrip("/") not in frontend_origins():
        return _rejected("Request origin is not allowed")

    if fetch_site in REJECTED_FETCH_SITES:
        return _rejected("Cross-site state changes are not allowed")

    return await call_next(request)
