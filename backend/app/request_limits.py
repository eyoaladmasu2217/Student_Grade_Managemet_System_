import os

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.audit import log_security_event
from app.config import ConfigurationError

DEFAULT_MAX_REQUEST_BYTES = 1024 * 1024
MIN_MAX_REQUEST_BYTES = 1024
BODY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def max_request_bytes() -> int:
    raw = os.getenv("SGMS_MAX_REQUEST_BYTES", str(DEFAULT_MAX_REQUEST_BYTES))
    try:
        limit = int(raw)
    except ValueError as error:
        raise ConfigurationError("SGMS_MAX_REQUEST_BYTES must be an integer") from error
    if limit < MIN_MAX_REQUEST_BYTES:
        raise ConfigurationError(
            f"SGMS_MAX_REQUEST_BYTES must be at least {MIN_MAX_REQUEST_BYTES}"
        )
    return limit


def _too_large(request: Request, limit: int) -> JSONResponse:
    log_security_event("request_body", "failure", reason="too_large", path=request.url.path)
    return JSONResponse(
        status_code=413,
        content={"detail": f"Request body exceeds {limit} bytes"},
    )


async def limit_request_body(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    limit = getattr(request.app.state, "max_request_bytes", None)
    if limit is None:
        limit = max_request_bytes()
    if request.method not in BODY_METHODS:
        return await call_next(request)

    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            length = int(declared)
        except ValueError:
            return _too_large(request, limit)
        if length > limit:
            return _too_large(request, limit)

    if len(await request.body()) > limit:
        return _too_large(request, limit)
    return await call_next(request)
