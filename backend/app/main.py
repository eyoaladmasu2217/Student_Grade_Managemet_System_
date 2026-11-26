from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from app.academic import router as academic_router
from app.auth import router as auth_router
from app.config import frontend_origins, is_production
from app.courses import course_router, section_router
from app.corrections import router as corrections_router
from app.csrf import validate_request_origin
from app.database import initialize_database, purge_expired_sessions
from app.enrollments import router as enrollments_router
from app.gradebook import router as gradebook_router
from app.grade_scale import router as grade_scale_router
from app.releases import router as releases_router
from app.scores import router as scores_router
from app.security_headers import add_security_headers
from app.simulation import router as simulation_router
from app.users import router as users_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    purge_expired_sessions()
    yield


async def handle_validation_error(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    if request.url.path == "/api/auth/login":
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Email or password is not acceptable"},
        )
    details = [
        {"type": item["type"], "loc": item["loc"], "msg": item["msg"]}
        for item in error.errors()
    ]
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": details}
    )


def create_app() -> FastAPI:
    production = is_production()
    origins = frontend_origins()
    api = FastAPI(
        title="Student Grade Management API",
        version="0.1.0",
        description="API for managing course assessments and student grades.",
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        lifespan=lifespan,
    )

    api.add_exception_handler(RequestValidationError, handle_validation_error)
    api.state.allowed_origins = frozenset(origins)

    api.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )
    api.middleware("http")(add_security_headers)
    api.middleware("http")(validate_request_origin)

    api.include_router(auth_router)
    api.include_router(academic_router)
    api.include_router(course_router)
    api.include_router(section_router)
    api.include_router(users_router)
    api.include_router(enrollments_router)
    api.include_router(gradebook_router)
    api.include_router(scores_router)
    api.include_router(grade_scale_router)
    api.include_router(releases_router)
    api.include_router(corrections_router)
    api.include_router(simulation_router)

    @api.get("/api/health", tags=["health"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return api


app = create_app()
