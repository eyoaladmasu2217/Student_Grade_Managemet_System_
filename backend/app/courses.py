import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.auth import get_current_user, require_roles
from app.database import get_db

course_router = APIRouter(prefix="/api/courses", tags=["courses"])
section_router = APIRouter(prefix="/api/sections", tags=["sections"])


class CourseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=24)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Course code cannot be blank")
        return normalized

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Course title cannot be blank")
        return normalized


class CourseResponse(BaseModel):
    id: int
    code: str
    title: str
    description: str


class SectionCreate(BaseModel):
    term_id: int = Field(gt=0)
    instructor_id: int = Field(gt=0)
    section_code: str = Field(min_length=1, max_length=32)

    @field_validator("section_code")
    @classmethod
    def normalize_section_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Section code cannot be blank")
        return normalized


class SectionResponse(BaseModel):
    id: int
    course_id: int
    course_code: str
    course_title: str
    term_id: int
    term_name: str
    academic_year_id: int
    instructor_id: int
    instructor_name: str
    section_code: str


def section_query() -> str:
    return """
        SELECT sections.id, sections.course_id, courses.code AS course_code,
               courses.title AS course_title, sections.term_id, terms.name AS term_name,
               terms.academic_year_id, sections.instructor_id,
               users.full_name AS instructor_name, sections.section_code
        FROM sections
        JOIN courses ON courses.id = sections.course_id
        JOIN terms ON terms.id = sections.term_id
        JOIN users ON users.id = sections.instructor_id
    """


@course_router.get("", response_model=list[CourseResponse])
def list_courses(
    _: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[CourseResponse]:
    rows = connection.execute(
        "SELECT id, code, title, description FROM courses ORDER BY code"
    ).fetchall()
    return [CourseResponse(**dict(row)) for row in rows]


@course_router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course(
    payload: CourseCreate,
    _: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> CourseResponse:
    try:
        cursor = connection.execute(
            "INSERT INTO courses (code, title, description) VALUES (?, ?, ?)",
            (payload.code, payload.title, payload.description.strip()),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A course with that code already exists",
            ) from error
        raise

    row = connection.execute(
        "SELECT id, code, title, description FROM courses WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return CourseResponse(**dict(row))


@course_router.post(
    "/{course_id}/sections",
    response_model=SectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_section(
    course_id: int,
    payload: SectionCreate,
    _: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> SectionResponse:
    course = connection.execute(
        "SELECT id FROM courses WHERE id = ?",
        (course_id,),
    ).fetchone()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    term = connection.execute(
        "SELECT id FROM terms WHERE id = ?",
        (payload.term_id,),
    ).fetchone()
    if term is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term not found")

    instructor = connection.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'instructor' AND is_active = 1",
        (payload.instructor_id,),
    ).fetchone()
    if instructor is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An active instructor account is required",
        )

    try:
        cursor = connection.execute(
            """
            INSERT INTO sections (course_id, term_id, instructor_id, section_code)
            VALUES (?, ?, ?, ?)
            """,
            (course_id, payload.term_id, payload.instructor_id, payload.section_code),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That section code is already used for this course and term",
            ) from error
        raise

    row = connection.execute(
        section_query() + " WHERE sections.id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return SectionResponse(**dict(row))


@course_router.get("/{course_id}/sections", response_model=list[SectionResponse])
def list_course_sections(
    course_id: int,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[SectionResponse]:
    course = connection.execute(
        "SELECT id FROM courses WHERE id = ?",
        (course_id,),
    ).fetchone()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    query = section_query() + " WHERE sections.course_id = ?"
    params: tuple[int, ...] = (course_id,)
    if user["role"] == "instructor":
        query += " AND sections.instructor_id = ?"
        params += (user["id"],)
    elif user["role"] == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student section access is available through enrollment",
        )
    query += " ORDER BY terms.start_date, sections.section_code"
    rows = connection.execute(query, params).fetchall()
    return [SectionResponse(**dict(row)) for row in rows]


@section_router.get("", response_model=list[SectionResponse])
def list_sections(
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[SectionResponse]:
    if user["role"] == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student section access is available through enrollment",
        )

    query = section_query()
    params: tuple[int, ...] = ()
    if user["role"] == "instructor":
        query += " WHERE sections.instructor_id = ?"
        params = (user["id"],)
    query += " ORDER BY terms.start_date DESC, courses.code, sections.section_code"
    rows = connection.execute(query, params).fetchall()
    return [SectionResponse(**dict(row)) for row in rows]
