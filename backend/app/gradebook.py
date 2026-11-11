import sqlite3
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.auth import get_current_user
from app.database import get_db

router = APIRouter(tags=["gradebook"])


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    weight: float = Field(gt=0, le=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Category name cannot be blank")
        return normalized


class CategoryWeightUpdate(BaseModel):
    weight: float = Field(gt=0, le=100)


class CategoryResponse(BaseModel):
    id: int
    section_id: int
    name: str
    weight: float


class AssessmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    max_points: float = Field(gt=0, le=100000)
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Assessment title cannot be blank")
        return normalized


class AssessmentResponse(BaseModel):
    id: int
    category_id: int
    category_name: str
    category_weight: float
    title: str
    max_points: float
    due_date: date | None


def require_section_manager(
    connection: sqlite3.Connection,
    section_id: int,
    user: sqlite3.Row,
) -> None:
    section = connection.execute(
        "SELECT instructor_id FROM sections WHERE id = ?",
        (section_id,),
    ).fetchone()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    if user["role"] != "admin" and (
        user["role"] != "instructor" or section["instructor_id"] != user["id"]
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


def require_category_manager(
    connection: sqlite3.Connection,
    category_id: int,
    user: sqlite3.Row,
) -> sqlite3.Row:
    category = connection.execute(
        "SELECT id, section_id FROM assessment_categories WHERE id = ?",
        (category_id,),
    ).fetchone()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    require_section_manager(connection, category["section_id"], user)
    return category


def require_gradebook_unreleased(
    connection: sqlite3.Connection,
    section_id: int,
) -> None:
    if connection.execute(
        "SELECT 1 FROM section_releases WHERE section_id = ?",
        (section_id,),
    ).fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assessment structure cannot change after grades have been released",
        )


@router.get(
    "/api/sections/{section_id}/categories",
    response_model=list[CategoryResponse],
)
def list_categories(
    section_id: int,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[CategoryResponse]:
    require_section_manager(connection, section_id, user)
    rows = connection.execute(
        """
        SELECT id, section_id, name, weight
        FROM assessment_categories
        WHERE section_id = ?
        ORDER BY name
        """,
        (section_id,),
    ).fetchall()
    return [CategoryResponse(**dict(row)) for row in rows]


@router.post(
    "/api/sections/{section_id}/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    section_id: int,
    payload: CategoryCreate,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> CategoryResponse:
    require_section_manager(connection, section_id, user)
    connection.execute("BEGIN IMMEDIATE")
    require_gradebook_unreleased(connection, section_id)
    total_weight = connection.execute(
        "SELECT COALESCE(SUM(weight), 0) AS total FROM assessment_categories WHERE section_id = ?",
        (section_id,),
    ).fetchone()["total"]
    if total_weight + payload.weight > 100.000001:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category weights cannot total more than 100%",
        )

    try:
        cursor = connection.execute(
            """
            INSERT INTO assessment_categories (section_id, name, weight)
            VALUES (?, ?, ?)
            """,
            (section_id, payload.name, payload.weight),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with that name already exists in this section",
            ) from error
        raise

    row = connection.execute(
        "SELECT id, section_id, name, weight FROM assessment_categories WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return CategoryResponse(**dict(row))


@router.patch(
    "/api/categories/{category_id}/weight",
    response_model=CategoryResponse,
)
def update_category_weight(
    category_id: int,
    payload: CategoryWeightUpdate,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> CategoryResponse:
    category = require_category_manager(connection, category_id, user)
    connection.execute("BEGIN IMMEDIATE")
    require_gradebook_unreleased(connection, category["section_id"])
    other_weight = connection.execute(
        """
        SELECT COALESCE(SUM(weight), 0) AS total
        FROM assessment_categories
        WHERE section_id = ? AND id != ?
        """,
        (category["section_id"], category_id),
    ).fetchone()["total"]
    if other_weight + payload.weight > 100.000001:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category weights cannot total more than 100%",
        )

    connection.execute(
        "UPDATE assessment_categories SET weight = ? WHERE id = ?",
        (payload.weight, category_id),
    )
    connection.commit()
    row = connection.execute(
        "SELECT id, section_id, name, weight FROM assessment_categories WHERE id = ?",
        (category_id,),
    ).fetchone()
    return CategoryResponse(**dict(row))


@router.get(
    "/api/sections/{section_id}/assessments",
    response_model=list[AssessmentResponse],
)
def list_assessments(
    section_id: int,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[AssessmentResponse]:
    require_section_manager(connection, section_id, user)
    rows = connection.execute(
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
    return [AssessmentResponse(**dict(row)) for row in rows]


@router.post(
    "/api/categories/{category_id}/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(
    category_id: int,
    payload: AssessmentCreate,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> AssessmentResponse:
    category = require_category_manager(connection, category_id, user)
    connection.execute("BEGIN IMMEDIATE")
    require_gradebook_unreleased(connection, category["section_id"])
    try:
        cursor = connection.execute(
            """
            INSERT INTO assessments (category_id, title, max_points, due_date)
            VALUES (?, ?, ?, ?)
            """,
            (
                category_id,
                payload.title,
                payload.max_points,
                payload.due_date.isoformat() if payload.due_date else None,
            ),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An assessment with that title already exists in this category",
            ) from error
        raise

    row = connection.execute(
        """
        SELECT assessments.id, assessments.category_id,
               assessment_categories.name AS category_name,
               assessment_categories.weight AS category_weight,
               assessments.title, assessments.max_points, assessments.due_date
        FROM assessments
        JOIN assessment_categories ON assessment_categories.id = assessments.category_id
        WHERE assessments.id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    return AssessmentResponse(**dict(row))
