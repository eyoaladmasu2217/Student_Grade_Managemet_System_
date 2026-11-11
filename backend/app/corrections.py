import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.auth import get_current_user
from app.database import get_db
from app.grade_math import calculate_grade_for_student
from app.grade_scale import letter_grade_for
from app.gradebook import require_section_manager

router = APIRouter(tags=["grade corrections"])


class GradeCorrectionInput(BaseModel):
    points: float = Field(ge=0, le=100000)
    reason: str = Field(min_length=8, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 8:
            raise ValueError("A correction reason must contain at least 8 characters")
        return normalized


class GradeCorrectionResponse(BaseModel):
    id: int
    section_id: int
    student_id: int
    student_name: str
    assessment_id: int
    assessment_title: str
    previous_points: float
    new_points: float
    previous_percentage: float
    new_percentage: float
    previous_letter_grade: str
    new_letter_grade: str
    changed_by: int
    changed_by_name: str
    reason: str
    changed_at: str


@router.put(
    "/api/assessments/{assessment_id}/scores/{student_id}/correction",
    response_model=GradeCorrectionResponse,
)
def correct_released_score(
    assessment_id: int,
    student_id: int,
    payload: GradeCorrectionInput,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> GradeCorrectionResponse:
    assessment = connection.execute(
        """
        SELECT assessments.id, assessments.title, assessments.max_points,
               assessment_categories.id AS category_id,
               assessment_categories.section_id
        FROM assessments
        JOIN assessment_categories ON assessment_categories.id = assessments.category_id
        WHERE assessments.id = ?
        """,
        (assessment_id,),
    ).fetchone()
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    require_section_manager(connection, assessment["section_id"], user)
    if payload.points > assessment["max_points"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Score cannot exceed {assessment['max_points']} points",
        )

    connection.execute("BEGIN IMMEDIATE")
    released_grade = connection.execute(
        """
        SELECT percentage, letter_grade
        FROM released_grades
        WHERE section_id = ? AND student_id = ?
        """,
        (assessment["section_id"], student_id),
    ).fetchone()
    if released_grade is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This student's grade has not been released",
        )

    prior_score = connection.execute(
        """
        SELECT points
        FROM assessment_scores
        WHERE assessment_id = ? AND student_id = ?
        """,
        (assessment_id, student_id),
    ).fetchone()
    if prior_score is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment score not found")

    changed_at = datetime.now(timezone.utc).isoformat()
    connection.execute(
        """
        UPDATE assessment_scores
        SET points = ?, updated_by = ?, updated_at = ?
        WHERE assessment_id = ? AND student_id = ?
        """,
        (payload.points, user["id"], changed_at, assessment_id, student_id),
    )
    new_summary = calculate_grade_for_student(
        connection,
        assessment["section_id"],
        student_id,
    )
    if not new_summary.is_complete or new_summary.final_percentage is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Corrected grade is incomplete and cannot be released",
        )
    new_letter_grade = letter_grade_for(connection, new_summary.final_percentage)
    if new_letter_grade is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Grade scale does not cover the corrected percentage",
        )

    connection.execute(
        """
        UPDATE released_grades
        SET percentage = ?, letter_grade = ?
        WHERE section_id = ? AND student_id = ?
        """,
        (
            new_summary.final_percentage,
            new_letter_grade,
            assessment["section_id"],
            student_id,
        ),
    )
    cursor = connection.execute(
        """
        INSERT INTO grade_corrections (
            section_id, student_id, assessment_id,
            previous_points, new_points,
            previous_percentage, new_percentage,
            previous_letter_grade, new_letter_grade,
            changed_by, reason, changed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            assessment["section_id"],
            student_id,
            assessment_id,
            prior_score["points"],
            payload.points,
            released_grade["percentage"],
            new_summary.final_percentage,
            released_grade["letter_grade"],
            new_letter_grade,
            user["id"],
            payload.reason,
            changed_at,
        ),
    )
    connection.commit()

    row = connection.execute(
        """
        SELECT grade_corrections.id, grade_corrections.section_id,
               grade_corrections.student_id, students.full_name AS student_name,
               grade_corrections.assessment_id, assessments.title AS assessment_title,
               grade_corrections.previous_points, grade_corrections.new_points,
               grade_corrections.previous_percentage, grade_corrections.new_percentage,
               grade_corrections.previous_letter_grade, grade_corrections.new_letter_grade,
               grade_corrections.changed_by, editors.full_name AS changed_by_name,
               grade_corrections.reason, grade_corrections.changed_at
        FROM grade_corrections
        JOIN users AS students ON students.id = grade_corrections.student_id
        JOIN users AS editors ON editors.id = grade_corrections.changed_by
        JOIN assessments ON assessments.id = grade_corrections.assessment_id
        WHERE grade_corrections.id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    return GradeCorrectionResponse(**dict(row))


@router.get(
    "/api/sections/{section_id}/corrections",
    response_model=list[GradeCorrectionResponse],
)
def list_grade_corrections(
    section_id: int,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[GradeCorrectionResponse]:
    require_section_manager(connection, section_id, user)
    rows = connection.execute(
        """
        SELECT grade_corrections.id, grade_corrections.section_id,
               grade_corrections.student_id, students.full_name AS student_name,
               grade_corrections.assessment_id, assessments.title AS assessment_title,
               grade_corrections.previous_points, grade_corrections.new_points,
               grade_corrections.previous_percentage, grade_corrections.new_percentage,
               grade_corrections.previous_letter_grade, grade_corrections.new_letter_grade,
               grade_corrections.changed_by, editors.full_name AS changed_by_name,
               grade_corrections.reason, grade_corrections.changed_at
        FROM grade_corrections
        JOIN users AS students ON students.id = grade_corrections.student_id
        JOIN users AS editors ON editors.id = grade_corrections.changed_by
        JOIN assessments ON assessments.id = grade_corrections.assessment_id
        WHERE grade_corrections.section_id = ?
        ORDER BY grade_corrections.changed_at DESC, grade_corrections.id DESC
        """,
        (section_id,),
    ).fetchall()
    return [GradeCorrectionResponse(**dict(row)) for row in rows]
