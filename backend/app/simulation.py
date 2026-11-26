import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import require_roles
from app.database import get_db
from app.grade_scale import load_grade_bands

router = APIRouter(tags=["grade simulation"])


class SimulationCategory(BaseModel):
    id: int
    name: str
    weight: float


class SimulationAssessment(BaseModel):
    id: int
    category_id: int
    title: str
    max_points: float
    due_date: str | None
    points: float | None


class SimulationBand(BaseModel):
    code: str
    minimum_percentage: float


class WhatIfSimulation(BaseModel):
    section_id: int
    course_code: str
    course_title: str
    section_code: str
    term_name: str
    grades_released: bool
    categories: list[SimulationCategory]
    assessments: list[SimulationAssessment]
    grade_bands: list[SimulationBand]


@router.get(
    "/api/sections/{section_id}/what-if",
    response_model=WhatIfSimulation,
)
def get_what_if_simulation(
    section_id: int,
    user: Annotated[sqlite3.Row, Depends(require_roles("student"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> WhatIfSimulation:
    enrollment = connection.execute(
        """
        SELECT 1 FROM enrollments
        WHERE section_id = ? AND student_id = ? AND status = 'active'
        """,
        (section_id, user["id"]),
    ).fetchone()
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    section = connection.execute(
        """
        SELECT sections.id, sections.section_code, courses.code AS course_code,
               courses.title AS course_title, terms.name AS term_name,
               CASE WHEN section_releases.section_id IS NULL THEN 0 ELSE 1 END
                   AS grades_released
        FROM sections
        JOIN courses ON courses.id = sections.course_id
        JOIN terms ON terms.id = sections.term_id
        LEFT JOIN section_releases ON section_releases.section_id = sections.id
        WHERE sections.id = ?
        """,
        (section_id,),
    ).fetchone()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    categories = connection.execute(
        """
        SELECT id, name, weight
        FROM assessment_categories
        WHERE section_id = ?
        ORDER BY id
        """,
        (section_id,),
    ).fetchall()
    grades_released = bool(section["grades_released"])
    assessments = connection.execute(
        """
        SELECT assessments.id, assessments.category_id, assessments.title,
               assessments.max_points, assessments.due_date,
               CASE WHEN ? = 1 THEN assessment_scores.points ELSE NULL END AS points
        FROM assessment_categories
        JOIN assessments ON assessments.category_id = assessment_categories.id
        LEFT JOIN assessment_scores
            ON assessment_scores.assessment_id = assessments.id
            AND assessment_scores.student_id = ?
        WHERE assessment_categories.section_id = ?
        ORDER BY assessments.id
        """,
        (1 if grades_released else 0, user["id"], section_id),
    ).fetchall()
    bands = load_grade_bands(connection)
    return WhatIfSimulation(
        section_id=section_id,
        course_code=section["course_code"],
        course_title=section["course_title"],
        section_code=section["section_code"],
        term_name=section["term_name"],
        grades_released=grades_released,
        categories=[SimulationCategory(**dict(row)) for row in categories],
        assessments=[SimulationAssessment(**dict(row)) for row in assessments],
        grade_bands=[SimulationBand(code=code, minimum_percentage=minimum) for minimum, code in bands],
    )
