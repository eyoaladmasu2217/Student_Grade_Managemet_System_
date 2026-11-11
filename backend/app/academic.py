import sqlite3
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth import get_current_user, require_roles
from app.database import get_db

router = APIRouter(prefix="/api/academic-years", tags=["academic structure"])


class DateRangeInput(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRangeInput":
        if self.start_date > self.end_date:
            raise ValueError("Start date must be on or before end date")
        return self


class AcademicYearCreate(DateRangeInput):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Academic year name cannot be blank")
        return normalized


class AcademicYearResponse(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date


class TermCreate(DateRangeInput):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Term name cannot be blank")
        return normalized


class TermResponse(BaseModel):
    id: int
    academic_year_id: int
    name: str
    start_date: date
    end_date: date


@router.get("", response_model=list[AcademicYearResponse])
def list_academic_years(
    _: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[AcademicYearResponse]:
    rows = connection.execute(
        "SELECT id, name, start_date, end_date FROM academic_years ORDER BY start_date DESC"
    ).fetchall()
    return [AcademicYearResponse(**dict(row)) for row in rows]


@router.post(
    "",
    response_model=AcademicYearResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_academic_year(
    payload: AcademicYearCreate,
    _: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> AcademicYearResponse:
    try:
        cursor = connection.execute(
            """
            INSERT INTO academic_years (name, start_date, end_date)
            VALUES (?, ?, ?)
            """,
            (payload.name.strip(), payload.start_date.isoformat(), payload.end_date.isoformat()),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An academic year with that name already exists",
            ) from error
        raise

    row = connection.execute(
        "SELECT id, name, start_date, end_date FROM academic_years WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return AcademicYearResponse(**dict(row))


@router.get("/{academic_year_id}/terms", response_model=list[TermResponse])
def list_terms(
    academic_year_id: int,
    _: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[TermResponse]:
    year = connection.execute(
        "SELECT id FROM academic_years WHERE id = ?",
        (academic_year_id,),
    ).fetchone()
    if year is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    rows = connection.execute(
        """
        SELECT id, academic_year_id, name, start_date, end_date
        FROM terms
        WHERE academic_year_id = ?
        ORDER BY start_date
        """,
        (academic_year_id,),
    ).fetchall()
    return [TermResponse(**dict(row)) for row in rows]


@router.post(
    "/{academic_year_id}/terms",
    response_model=TermResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_term(
    academic_year_id: int,
    payload: TermCreate,
    _: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> TermResponse:
    year = connection.execute(
        "SELECT start_date, end_date FROM academic_years WHERE id = ?",
        (academic_year_id,),
    ).fetchone()
    if year is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")
    if payload.start_date.isoformat() < year["start_date"] or payload.end_date.isoformat() > year["end_date"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Term dates must fall within the academic year",
        )

    try:
        cursor = connection.execute(
            """
            INSERT INTO terms (academic_year_id, name, start_date, end_date)
            VALUES (?, ?, ?, ?)
            """,
            (
                academic_year_id,
                payload.name.strip(),
                payload.start_date.isoformat(),
                payload.end_date.isoformat(),
            ),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A term with that name already exists in this academic year",
            ) from error
        raise

    row = connection.execute(
        """
        SELECT id, academic_year_id, name, start_date, end_date
        FROM terms
        WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    return TermResponse(**dict(row))
