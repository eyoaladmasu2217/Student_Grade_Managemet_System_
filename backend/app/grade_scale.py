import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.auth import get_current_user, require_roles
from app.database import get_db

router = APIRouter(prefix="/api/grade-scale", tags=["grade scale"])


class GradeBandInput(BaseModel):
    code: str = Field(min_length=1, max_length=8)
    minimum_percentage: float = Field(ge=0, le=100)


class GradeScaleUpdate(BaseModel):
    bands: list[GradeBandInput] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def validate_scale(self) -> "GradeScaleUpdate":
        codes = [band.code.strip().upper() for band in self.bands]
        thresholds = [band.minimum_percentage for band in self.bands]
        if any(not code for code in codes):
            raise ValueError("Grade band codes cannot be blank")
        if len(set(codes)) != len(codes):
            raise ValueError("Grade band codes must be unique")
        if len(set(thresholds)) != len(thresholds):
            raise ValueError("Grade thresholds must be unique")
        if 0 not in thresholds:
            raise ValueError("A grade band must start at 0% to cover every score")
        return self


class GradeBandResponse(BaseModel):
    code: str
    minimum_percentage: float


@router.get("", response_model=list[GradeBandResponse])
def get_grade_scale(
    _: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[GradeBandResponse]:
    rows = connection.execute(
        "SELECT code, minimum_percentage FROM grade_bands ORDER BY minimum_percentage DESC"
    ).fetchall()
    return [GradeBandResponse(**dict(row)) for row in rows]


@router.put("", response_model=list[GradeBandResponse])
def update_grade_scale(
    payload: GradeScaleUpdate,
    _: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> list[GradeBandResponse]:
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("DELETE FROM grade_bands")
    connection.executemany(
        "INSERT INTO grade_bands (code, minimum_percentage) VALUES (?, ?)",
        [
            (band.code.strip().upper(), band.minimum_percentage)
            for band in payload.bands
        ],
    )
    connection.commit()
    rows = connection.execute(
        "SELECT code, minimum_percentage FROM grade_bands ORDER BY minimum_percentage DESC"
    ).fetchall()
    return [GradeBandResponse(**dict(row)) for row in rows]


def letter_grade_for(
    connection: sqlite3.Connection,
    percentage: float | None,
) -> str | None:
    if percentage is None:
        return None
    row = connection.execute(
        """
        SELECT code
        FROM grade_bands
        WHERE minimum_percentage <= ?
        ORDER BY minimum_percentage DESC
        LIMIT 1
        """,
        (percentage,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Grade scale does not cover this percentage",
        )
    return row["code"]
