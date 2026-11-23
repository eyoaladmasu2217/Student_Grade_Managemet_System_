import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.audit import log_security_event
from app.auth import UserResponse, require_roles
from app.database import get_db
from app.password_policy import validate_password
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

    @model_validator(mode="after")
    def check_password_strength(self) -> "UserCreate":
        validate_password(self.password, str(self.email))
        return self


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
            SELECT id, email, full_name, role, is_active
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
            SELECT id, email, full_name, role, is_active
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
    administrator: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
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
        "SELECT id, email, full_name, role, is_active FROM users WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    log_security_event(
        "user_created",
        "success",
        administrator_id=administrator["id"],
        user_id=row["id"],
        role=row["role"],
    )
    return UserResponse(**dict(row))


class UserActiveInput(BaseModel):
    is_active: bool


@router.patch("/{user_id}/active", response_model=UserResponse)
def set_user_active(
    user_id: int,
    payload: UserActiveInput,
    administrator: Annotated[sqlite3.Row, Depends(require_roles("admin"))],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> UserResponse:
    connection.execute("BEGIN IMMEDIATE")
    target = connection.execute(
        "SELECT id, is_active FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not payload.is_active and target["id"] == administrator["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account",
        )

    connection.execute(
        "UPDATE users SET is_active = ? WHERE id = ?",
        (int(payload.is_active), user_id),
    )
    if not payload.is_active:
        connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    connection.commit()

    row = connection.execute(
        "SELECT id, email, full_name, role, is_active FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    log_security_event(
        "account_status_changed",
        "success",
        administrator_id=administrator["id"],
        user_id=user_id,
        is_active=payload.is_active,
    )
    return UserResponse(**dict(row))
