import sqlite3
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.database import get_db
from app.grade_math import calculate_grade_for_student
from app.gradebook import require_category_manager, require_section_manager
from app.grade_scale import letter_grade_for

router = APIRouter(tags=["scores"])


class ScoreInput(BaseModel):
    points: float = Field(ge=0, le=100000)


class ScoreResponse(BaseModel):
    assessment_id: int
    student_id: int
    points: float
    max_points: float
    updated_by: int
    updated_at: str


class AssessmentInGradebook(BaseModel):
    id: int
    category_id: int
    category_name: str
    category_weight: float
    title: str
    max_points: float
    due_date: str | None


class StudentGradebookRow(BaseModel):
    student_id: int
    student_name: str
    student_email: str
    scores: dict[int, float]
    weighted_points: float
    graded_weight: float
    current_percentage: float | None
    final_percentage: float | None
    letter_grade: str | None
    is_complete: bool


class GradebookResponse(BaseModel):
    section_id: int
    assessments: list[AssessmentInGradebook]
    students: list[StudentGradebookRow]


@router.put(
    "/api/assessments/{assessment_id}/scores/{student_id}",
    response_model=ScoreResponse,
)
def record_score(
    assessment_id: int,
    student_id: int,
    payload: ScoreInput,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> ScoreResponse:
    assessment = connection.execute(
        """
        SELECT assessments.id, assessments.max_points, assessment_categories.id AS category_id,
               assessment_categories.section_id
        FROM assessments
        JOIN assessment_categories ON assessment_categories.id = assessments.category_id
        WHERE assessments.id = ?
        """,
        (assessment_id,),
    ).fetchone()
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    require_category_manager(connection, assessment["category_id"], user)

    if payload.points > assessment["max_points"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Score cannot exceed {assessment['max_points']} points",
        )

    enrollment = connection.execute(
        """
        SELECT id FROM enrollments
        WHERE section_id = ? AND student_id = ? AND status = 'active'
        """,
        (assessment["section_id"], student_id),
    ).fetchone()
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active student enrollment not found for this section",
        )

    updated_at = datetime.now(timezone.utc).isoformat()
    connection.execute(
        """
        INSERT INTO assessment_scores (assessment_id, student_id, points, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (assessment_id, student_id)
        DO UPDATE SET points = excluded.points,
                      updated_by = excluded.updated_by,
                      updated_at = excluded.updated_at
        """,
        (assessment_id, student_id, payload.points, user["id"], updated_at),
    )
    connection.commit()
    row = connection.execute(
        """
        SELECT assessment_scores.assessment_id, assessment_scores.student_id,
               assessment_scores.points, assessments.max_points,
               assessment_scores.updated_by, assessment_scores.updated_at
        FROM assessment_scores
        JOIN assessments ON assessments.id = assessment_scores.assessment_id
        WHERE assessment_scores.assessment_id = ? AND assessment_scores.student_id = ?
        """,
        (assessment_id, student_id),
    ).fetchone()
    return ScoreResponse(**dict(row))


@router.get(
    "/api/sections/{section_id}/gradebook",
    response_model=GradebookResponse,
)
def get_gradebook(
    section_id: int,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> GradebookResponse:
    require_section_manager(connection, section_id, user)
    assessments = connection.execute(
        """
        SELECT assessments.id, assessments.category_id,
               assessment_categories.name AS category_name,
               assessment_categories.weight AS category_weight,
               assessments.title, assessments.max_points, assessments.due_date
        FROM assessments
        JOIN assessment_categories ON assessment_categories.id = assessments.category_id
        WHERE assessment_categories.section_id = ?
        ORDER BY assessment_categories.name, assessments.due_date, assessments.title
        """,
        (section_id,),
    ).fetchall()
    assessment_responses = [
        AssessmentInGradebook(**dict(row)) for row in assessments
    ]

    students = connection.execute(
        """
        SELECT users.id, users.full_name, users.email
        FROM enrollments
        JOIN users ON users.id = enrollments.student_id
        WHERE enrollments.section_id = ? AND enrollments.status = 'active'
        ORDER BY users.full_name, users.email
        """,
        (section_id,),
    ).fetchall()
    grade_rows: list[StudentGradebookRow] = []
    for student in students:
        scores = connection.execute(
            """
            SELECT assessment_id, points
            FROM assessment_scores
            WHERE student_id = ? AND assessment_id IN (
                SELECT assessments.id
                FROM assessments
                JOIN assessment_categories
                    ON assessment_categories.id = assessments.category_id
                WHERE assessment_categories.section_id = ?
            )
            """,
            (student["id"], section_id),
        ).fetchall()
        summary = calculate_grade_for_student(connection, section_id, student["id"])
        grade_rows.append(
            StudentGradebookRow(
                student_id=student["id"],
                student_name=student["full_name"],
                student_email=student["email"],
                scores={row["assessment_id"]: row["points"] for row in scores},
                weighted_points=summary.weighted_points,
                graded_weight=summary.graded_weight,
                current_percentage=summary.current_percentage,
                final_percentage=summary.final_percentage,
                letter_grade=letter_grade_for(connection, summary.final_percentage),
                is_complete=summary.is_complete,
            )
        )

    return GradebookResponse(
        section_id=section_id,
        assessments=assessment_responses,
        students=grade_rows,
    )
