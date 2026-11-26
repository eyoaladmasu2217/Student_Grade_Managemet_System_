import sqlite3
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from app.audit import log_security_event
from app.auth import get_current_user, require_roles
from app.database import get_db
from app.grade_math import calculate_grade_for_student, calculate_grade_with_score
from app.grade_scale import letter_grade_for
from app.gradebook import require_section_manager

router = APIRouter(tags=["grade corrections"])

ReasonCode = Literal["grading_error", "misgraded_work", "data_entry", "retake", "other"]
ChangeStatus = Literal["pending", "approved", "rejected"]

CORRECTION_SELECT = """
    SELECT grade_corrections.id, grade_corrections.section_id,
           grade_corrections.student_id, students.full_name AS student_name,
           grade_corrections.assessment_id, assessments.title AS assessment_title,
           grade_corrections.previous_points, grade_corrections.new_points,
           grade_corrections.previous_percentage, grade_corrections.new_percentage,
           grade_corrections.previous_letter_grade, grade_corrections.new_letter_grade,
           grade_corrections.changed_by, editors.full_name AS changed_by_name,
           grade_corrections.reason, grade_corrections.reason_code,
           grade_corrections.status,
           COALESCE(grade_corrections.requested_by, grade_corrections.changed_by)
               AS requested_by,
           requesters.full_name AS requested_by_name,
           grade_corrections.reviewed_by, reviewers.full_name AS reviewed_by_name,
           grade_corrections.reviewed_at, grade_corrections.review_note,
           grade_corrections.changed_at
    FROM grade_corrections
    JOIN users AS students ON students.id = grade_corrections.student_id
    JOIN users AS editors ON editors.id = grade_corrections.changed_by
    JOIN users AS requesters
        ON requesters.id = COALESCE(grade_corrections.requested_by, grade_corrections.changed_by)
    LEFT JOIN users AS reviewers ON reviewers.id = grade_corrections.reviewed_by
    JOIN assessments ON assessments.id = grade_corrections.assessment_id
"""


class GradeCorrectionInput(BaseModel):
    points: float = Field(ge=0, le=100000)
    reason_code: ReasonCode
    reason: str = Field(min_length=8, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 8:
            raise ValueError("A correction reason must contain at least 8 characters")
        return normalized


class ApprovalInput(BaseModel):
    note: str = Field(default="", max_length=1000)


class RejectionInput(BaseModel):
    note: str = Field(min_length=8, max_length=1000)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 8:
            raise ValueError("A rejection note must contain at least 8 characters")
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
    reason_code: str
    status: str
    requested_by: int
    requested_by_name: str
    reviewed_by: int | None
    reviewed_by_name: str | None
    reviewed_at: str | None
    review_note: str | None
    changed_at: str


class GradeChangeEventResponse(BaseModel):
    id: int
    correction_id: int
    event: str
    actor_id: int
    actor_name: str
    note: str
    occurred_at: str


def record_change_event(
    connection: sqlite3.Connection,
    correction_id: int,
    section_id: int,
    event: str,
    actor_id: int,
    note: str,
    occurred_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO grade_change_events (
            correction_id, section_id, event, actor_id, note, occurred_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (correction_id, section_id, event, actor_id, note, occurred_at),
    )


def correction_response(
    connection: sqlite3.Connection, correction_id: int
) -> GradeCorrectionResponse:
    row = connection.execute(
        CORRECTION_SELECT + " WHERE grade_corrections.id = ?", (correction_id,)
    ).fetchone()
    return GradeCorrectionResponse(**dict(row))


def validate_change_target(
    connection: sqlite3.Connection,
    assessment_id: int,
    student_id: int,
    points: float,
    user: sqlite3.Row,
) -> tuple[sqlite3.Row, sqlite3.Row, sqlite3.Row]:
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
    if points > assessment["max_points"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Score cannot exceed {assessment['max_points']} points",
        )

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

    enrollment = connection.execute(
        """
        SELECT 1 FROM enrollments
        WHERE section_id = ? AND student_id = ? AND status = 'active'
        """,
        (assessment["section_id"], student_id),
    ).fetchone()
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active student enrollment not found for this section",
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
    return assessment, released_grade, prior_score


def apply_approved_change(
    connection: sqlite3.Connection,
    assessment: sqlite3.Row,
    student_id: int,
    points: float,
    applied_by: int,
) -> tuple[float, str]:
    changed_at = datetime.now(timezone.utc).isoformat()
    connection.execute(
        """
        UPDATE assessment_scores
        SET points = ?, updated_by = ?, updated_at = ?
        WHERE assessment_id = ? AND student_id = ?
        """,
        (points, applied_by, changed_at, assessment["id"], student_id),
    )
    summary = calculate_grade_for_student(
        connection,
        assessment["section_id"],
        student_id,
    )
    if not summary.is_complete or summary.final_percentage is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Corrected grade is incomplete and cannot be released",
        )
    letter_grade = letter_grade_for(connection, summary.final_percentage)
    if letter_grade is None:
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
        (summary.final_percentage, letter_grade, assessment["section_id"], student_id),
    )
    return summary.final_percentage, letter_grade


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
    connection.execute("BEGIN IMMEDIATE")
    assessment, released_grade, prior_score = validate_change_target(
        connection, assessment_id, student_id, payload.points, user
    )
    hypothetical = calculate_grade_with_score(
        connection, assessment["section_id"], student_id, assessment_id, payload.points
    )
    if not hypothetical.is_complete or hypothetical.final_percentage is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Corrected grade is incomplete and cannot be released",
        )
    new_letter_grade = letter_grade_for(connection, hypothetical.final_percentage)
    if new_letter_grade is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Grade scale does not cover the corrected percentage",
        )

    changed_at = datetime.now(timezone.utc).isoformat()
    approved = user["role"] == "admin"
    cursor = connection.execute(
        """
        INSERT INTO grade_corrections (
            section_id, student_id, assessment_id,
            previous_points, new_points,
            previous_percentage, new_percentage,
            previous_letter_grade, new_letter_grade,
            changed_by, reason, reason_code, status, requested_by,
            reviewed_by, reviewed_at, review_note, changed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            assessment["section_id"],
            student_id,
            assessment_id,
            prior_score["points"],
            payload.points,
            released_grade["percentage"],
            hypothetical.final_percentage,
            released_grade["letter_grade"],
            new_letter_grade,
            user["id"],
            payload.reason,
            payload.reason_code,
            "approved" if approved else "pending",
            user["id"],
            user["id"] if approved else None,
            changed_at if approved else None,
            "" if approved else None,
            changed_at,
        ),
    )
    correction_id = cursor.lastrowid
    record_change_event(
        connection,
        correction_id,
        assessment["section_id"],
        "requested",
        user["id"],
        payload.reason,
        changed_at,
    )

    if approved:
        apply_approved_change(
            connection, assessment, student_id, payload.points, user["id"]
        )
        record_change_event(
            connection,
            correction_id,
            assessment["section_id"],
            "approved",
            user["id"],
            "Approved by academic administrator",
            changed_at,
        )
    connection.commit()
    log_security_event(
        "grade_corrected" if approved else "grade_change_requested",
        "success",
        user_id=user["id"],
        section_id=assessment["section_id"],
        student_id=student_id,
        assessment_id=assessment_id,
        correction_id=correction_id,
    )
    return correction_response(connection, correction_id)


@router.get(
    "/api/grade-change-requests",
    response_model=list[GradeCorrectionResponse],
)
def list_grade_change_requests(
    user: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
    status_filter: ChangeStatus = Query(default="pending", alias="status"),
) -> list[GradeCorrectionResponse]:
    rows = connection.execute(
        CORRECTION_SELECT
        + " WHERE grade_corrections.status = ?"
        + " ORDER BY grade_corrections.changed_at DESC, grade_corrections.id DESC",
        (status_filter,),
    ).fetchall()
    return [GradeCorrectionResponse(**dict(row)) for row in rows]


@router.post(
    "/api/grade-change-requests/{correction_id}/approve",
    response_model=GradeCorrectionResponse,
)
def approve_grade_change(
    correction_id: int,
    payload: ApprovalInput,
    user: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> GradeCorrectionResponse:
    connection.execute("BEGIN IMMEDIATE")
    row = connection.execute(
        CORRECTION_SELECT + " WHERE grade_corrections.id = ?", (correction_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grade change request not found")
    if row["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This grade change request has already been reviewed",
        )

    assessment = connection.execute(
        """
        SELECT assessments.id, assessments.section_id, assessments.max_points
        FROM assessments WHERE assessments.id = ?
        """,
        (row["assessment_id"],),
    ).fetchone()
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    enrollment = connection.execute(
        """
        SELECT 1 FROM enrollments
        WHERE section_id = ? AND student_id = ? AND status = 'active'
        """,
        (row["section_id"], row["student_id"]),
    ).fetchone()
    released_grade = connection.execute(
        """
        SELECT 1 FROM released_grades
        WHERE section_id = ? AND student_id = ?
        """,
        (row["section_id"], row["student_id"]),
    ).fetchone()
    if enrollment is None or released_grade is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The student is no longer eligible for this grade change",
        )

    percentage, letter_grade = apply_approved_change(
        connection, assessment, row["student_id"], row["new_points"], user["id"]
    )
    reviewed_at = datetime.now(timezone.utc).isoformat()
    connection.execute(
        """
        UPDATE grade_corrections
        SET status = 'approved', reviewed_by = ?, reviewed_at = ?,
            review_note = ?, new_percentage = ?, new_letter_grade = ?
        WHERE id = ?
        """,
        (
            user["id"],
            reviewed_at,
            payload.note.strip(),
            percentage,
            letter_grade,
            correction_id,
        ),
    )
    record_change_event(
        connection,
        correction_id,
        row["section_id"],
        "approved",
        user["id"],
        payload.note.strip() or "Approved by academic administrator",
        reviewed_at,
    )
    connection.commit()
    log_security_event(
        "grade_change_approved",
        "success",
        user_id=user["id"],
        section_id=row["section_id"],
        correction_id=correction_id,
    )
    return correction_response(connection, correction_id)


@router.post(
    "/api/grade-change-requests/{correction_id}/reject",
    response_model=GradeCorrectionResponse,
)
def reject_grade_change(
    correction_id: int,
    payload: RejectionInput,
    user: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> GradeCorrectionResponse:
    connection.execute("BEGIN IMMEDIATE")
    row = connection.execute(
        "SELECT id, section_id, status FROM grade_corrections WHERE id = ?",
        (correction_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grade change request not found")
    if row["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This grade change request has already been reviewed",
        )
    reviewed_at = datetime.now(timezone.utc).isoformat()
    connection.execute(
        """
        UPDATE grade_corrections
        SET status = 'rejected', reviewed_by = ?, reviewed_at = ?, review_note = ?
        WHERE id = ?
        """,
        (user["id"], reviewed_at, payload.note, correction_id),
    )
    record_change_event(
        connection,
        correction_id,
        row["section_id"],
        "rejected",
        user["id"],
        payload.note,
        reviewed_at,
    )
    connection.commit()
    log_security_event(
        "grade_change_rejected",
        "success",
        user_id=user["id"],
        section_id=row["section_id"],
        correction_id=correction_id,
    )
    return correction_response(connection, correction_id)


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
        CORRECTION_SELECT
        + " WHERE grade_corrections.section_id = ?"
        + " ORDER BY grade_corrections.changed_at DESC, grade_corrections.id DESC",
        (section_id,),
    ).fetchall()
    return [GradeCorrectionResponse(**dict(row)) for row in rows]


@router.get(
    "/api/sections/{section_id}/audit-trail",
    response_model=list[GradeChangeEventResponse],
)
def list_grade_change_events(
    section_id: int,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[GradeChangeEventResponse]:
    require_section_manager(connection, section_id, user)
    rows = connection.execute(
        """
        SELECT grade_change_events.id, grade_change_events.correction_id,
               grade_change_events.event, grade_change_events.actor_id,
               users.full_name AS actor_name, grade_change_events.note,
               grade_change_events.occurred_at
        FROM grade_change_events
        JOIN users ON users.id = grade_change_events.actor_id
        WHERE grade_change_events.section_id = ?
        ORDER BY grade_change_events.occurred_at DESC, grade_change_events.id DESC
        """,
        (section_id,),
    ).fetchall()
    return [GradeChangeEventResponse(**dict(row)) for row in rows]
