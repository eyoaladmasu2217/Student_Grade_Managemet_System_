import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.auth import UserResponse, require_roles
from app.database import get_db
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])
UserRole = Literal["admin", "instructor", "student"]


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=128)
    role: UserRole

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank")
        return normalized


@router.get("", response_model=list[UserResponse])
def list_users(
    _: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
    role: UserRole | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserResponse]:
    if role:
        rows = connection.execute(
            """
            SELECT id, email, full_name, role
            FROM users
            WHERE role = ?
            ORDER BY full_name, email
            LIMIT ? OFFSET ?
            """,
            (role, limit, offset),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT id, email, full_name, role
            FROM users
            ORDER BY full_name, email
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [UserResponse(**dict(row)) for row in rows]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    _: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> UserResponse:
    try:
        cursor = connection.execute(
            """
            INSERT INTO users (email, full_name, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(payload.email).strip().lower(),
                payload.full_name,
                hash_password(payload.password),
                payload.role,
            ),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with that email already exists",
            ) from error
        raise

    row = connection.execute(
        "SELECT id, email, full_name, role FROM users WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return UserResponse(**dict(row))
