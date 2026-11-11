from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.academic import router as academic_router
from app.auth import router as auth_router
from app.courses import course_router, section_router
from app.database import initialize_database
from app.enrollments import router as enrollments_router
from app.gradebook import router as gradebook_router
from app.grade_scale import router as grade_scale_router
from app.scores import router as scores_router
from app.users import router as users_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield


app = FastAPI(
    title="Student Grade Management API",
    version="0.1.0",
    description="API for managing course assessments and student grades.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(academic_router)
app.include_router(course_router)
app.include_router(section_router)
app.include_router(users_router)
app.include_router(enrollments_router)
app.include_router(gradebook_router)
app.include_router(scores_router)
app.include_router(grade_scale_router)


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
