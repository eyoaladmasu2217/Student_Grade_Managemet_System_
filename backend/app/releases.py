import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.grade_math import calculate_grade_for_student
from app.grade_scale import letter_grade_for
from app.gradebook import require_section_manager

router = APIRouter(tags=["grade release"])


class ReleasedGradeResponse(BaseModel):
    section_id: int
    course_code: str
    course_title: str
    section_code: str
    term_name: str
    percentage: float
    letter_grade: str
    released_at: str


class ReleaseResult(BaseModel):
    section_id: int
    released_at: str
    student_count: int


@router.post(
    "/api/sections/{section_id}/release",
    response_model=ReleaseResult,
)
def release_section_grades(
    section_id: int,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> ReleaseResult:
    require_section_manager(connection, section_id, user)
    connection.execute("BEGIN IMMEDIATE")
    if connection.execute(
        "SELECT 1 FROM section_releases WHERE section_id = ?",
        (section_id,),
    ).fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Grades for this section have already been released",
        )

    students = connection.execute(
        """
        SELECT users.id
        FROM enrollments
        JOIN users ON users.id = enrollments.student_id
        WHERE enrollments.section_id = ?
          AND enrollments.status = 'active'
          AND users.is_active = 1
        ORDER BY users.id
        """,
        (section_id,),
    ).fetchall()
    if not students:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A section must have active students before grades can be released",
        )

    grades: list[tuple[int, float, str]] = []
    incomplete_student_ids: list[int] = []
    for student in students:
        summary = calculate_grade_for_student(connection, section_id, student["id"])
        if not summary.is_complete or summary.final_percentage is None:
            incomplete_student_ids.append(student["id"])
            continue
        letter_grade = letter_grade_for(connection, summary.final_percentage)
        if letter_grade is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Grade scale does not cover every final percentage",
            )
        grades.append((student["id"], summary.final_percentage, letter_grade))

    if incomplete_student_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "All category weights and student assessment scores must be complete",
                "incomplete_student_ids": incomplete_student_ids,
            },
        )

    released_at = datetime.now(timezone.utc).isoformat()
    connection.execute(
        "INSERT INTO section_releases (section_id, released_by, released_at) VALUES (?, ?, ?)",
        (section_id, user["id"], released_at),
    )
    connection.executemany(
        """
        INSERT INTO released_grades (section_id, student_id, percentage, letter_grade)
        VALUES (?, ?, ?, ?)
        """,
        [(section_id, student_id, percentage, letter) for student_id, percentage, letter in grades],
    )
    connection.commit()
    return ReleaseResult(
        section_id=section_id,
        released_at=released_at,
        student_count=len(grades),
    )


@router.get(
    "/api/sections/{section_id}/my-grade",
    response_model=ReleasedGradeResponse,
)
def get_my_released_grade(
    section_id: int,
    user: Annotated[sqlite3.Row, Depends(require_roles("student"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> ReleasedGradeResponse:
    enrollment = connection.execute(
        """
        SELECT 1 FROM enrollments
        WHERE section_id = ? AND student_id = ? AND status = 'active'
        """,
        (section_id, user["id"]),
    ).fetchone()
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    row = connection.execute(
        """
        SELECT released_grades.section_id, courses.code AS course_code,
               courses.title AS course_title, sections.section_code,
               terms.name AS term_name, released_grades.percentage,
               released_grades.letter_grade, section_releases.released_at
        FROM released_grades
        JOIN section_releases ON section_releases.section_id = released_grades.section_id
        JOIN sections ON sections.id = released_grades.section_id
        JOIN courses ON courses.id = sections.course_id
        JOIN terms ON terms.id = sections.term_id
        WHERE released_grades.section_id = ? AND released_grades.student_id = ?
        """,
        (section_id, user["id"]),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Grades for this section have not been released",
        )
    return ReleasedGradeResponse(**dict(row))


@router.get(
    "/api/enrollments/mine/grades",
    response_model=list[ReleasedGradeResponse],
)
def list_my_released_grades(
    user: Annotated[sqlite3.Row, Depends(require_roles("student"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[ReleasedGradeResponse]:
    rows = connection.execute(
        """
        SELECT released_grades.section_id, courses.code AS course_code,
               courses.title AS course_title, sections.section_code,
               terms.name AS term_name, released_grades.percentage,
               released_grades.letter_grade, section_releases.released_at
        FROM released_grades
        JOIN section_releases ON section_releases.section_id = released_grades.section_id
        JOIN sections ON sections.id = released_grades.section_id
        JOIN courses ON courses.id = sections.course_id
        JOIN terms ON terms.id = sections.term_id
        WHERE released_grades.student_id = ?
        ORDER BY section_releases.released_at DESC, courses.code
        """,
        (user["id"],),
    ).fetchall()
    return [ReleasedGradeResponse(**dict(row)) for row in rows]
