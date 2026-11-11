import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import get_current_user, require_roles
from app.courses import SectionResponse, section_query
from app.database import get_db

router = APIRouter(tags=["enrollments"])


class EnrollmentCreate(BaseModel):
    student_id: int = Field(gt=0)


class EnrollmentResponse(BaseModel):
    id: int
    section_id: int
    student_id: int
    student_name: str
    student_email: str
    status: Literal["active", "withdrawn"]


@router.post(
    "/api/sections/{section_id}/enrollments",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def enroll_student(
    section_id: int,
    payload: EnrollmentCreate,
    _: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> EnrollmentResponse:
    section = connection.execute(
        "SELECT id FROM sections WHERE id = ?",
        (section_id,),
    ).fetchone()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    student = connection.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'student' AND is_active = 1",
        (payload.student_id,),
    ).fetchone()
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An active student account is required",
        )

    try:
        cursor = connection.execute(
            "INSERT INTO enrollments (section_id, student_id) VALUES (?, ?)",
            (section_id, payload.student_id),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Student is already enrolled in this section",
            ) from error
        raise

    row = connection.execute(
        """
        SELECT enrollments.id, enrollments.section_id, enrollments.student_id,
               users.full_name AS student_name, users.email AS student_email,
               enrollments.status
        FROM enrollments
        JOIN users ON users.id = enrollments.student_id
        WHERE enrollments.id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    return EnrollmentResponse(**dict(row))


@router.get(
    "/api/sections/{section_id}/enrollments",
    response_model=list[EnrollmentResponse],
)
def list_section_enrollments(
    section_id: int,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[EnrollmentResponse]:
    section = connection.execute(
        "SELECT id, instructor_id FROM sections WHERE id = ?",
        (section_id,),
    ).fetchone()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    if user["role"] == "student" or (
        user["role"] == "instructor" and section["instructor_id"] != user["id"]
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    rows = connection.execute(
        """
        SELECT enrollments.id, enrollments.section_id, enrollments.student_id,
               users.full_name AS student_name, users.email AS student_email,
               enrollments.status
        FROM enrollments
        JOIN users ON users.id = enrollments.student_id
        WHERE enrollments.section_id = ? AND enrollments.status = 'active'
        ORDER BY users.full_name, users.email
        """,
        (section_id,),
    ).fetchall()
    return [EnrollmentResponse(**dict(row)) for row in rows]


@router.get("/api/enrollments/mine", response_model=list[SectionResponse])
def list_my_sections(
    user: Annotated[sqlite3.Row, Depends(require_roles("student"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[SectionResponse]:
    rows = connection.execute(
        section_query()
        + """
        JOIN enrollments ON enrollments.section_id = sections.id
        WHERE enrollments.student_id = ? AND enrollments.status = 'active'
        ORDER BY terms.start_date DESC, courses.code, sections.section_code
        """,
        (user["id"],),
    ).fetchall()
    return [SectionResponse(**dict(row)) for row in rows]
