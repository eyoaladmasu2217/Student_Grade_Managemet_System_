import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.database import get_db
from app.security import create_session_token, hash_session_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["authentication"])
SESSION_COOKIE = "sgms_session"
SESSION_DURATION = timedelta(hours=12)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str


def get_current_user(
    request: Request,
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> sqlite3.Row:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")

    row = connection.execute(
        """
        SELECT users.id, users.email, users.full_name, users.role, users.is_active,
               sessions.id AS session_id, sessions.expires_at
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ?
        """,
        (hash_session_token(token),),
    ).fetchone()
    if row is None or not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid")

    expiry = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if expiry <= datetime.now(timezone.utc):
        connection.execute("DELETE FROM sessions WHERE id = ?", (row["session_id"],))
        connection.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired")
    return row


def require_roles(*roles: str):
    def role_guard(
        user: Annotated[sqlite3.Row, Depends(get_current_user)],
    ) -> sqlite3.Row:
        if user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return role_guard


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    response: Response,
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> UserResponse:
    user = connection.execute(
        "SELECT id, email, full_name, password_hash, role, is_active FROM users WHERE email = ?",
        (str(payload.email),),
    ).fetchone()
    if user is None or not user["is_active"] or not verify_password(
        payload.password, user["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
        )

    token = create_session_token()
    expires_at = datetime.now(timezone.utc) + SESSION_DURATION
    connection.execute(
        "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (user["id"], hash_session_token(token), expires_at.isoformat()),
    )
    connection.commit()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=os.getenv("SGMS_COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=int(SESSION_DURATION.total_seconds()),
        path="/",
    )
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        connection.execute(
            "DELETE FROM sessions WHERE token_hash = ?",
            (hash_session_token(token),),
        )
        connection.commit()
    response.delete_cookie(key=SESSION_COOKIE, path="/", httponly=True, samesite="lax")


@router.get("/me", response_model=UserResponse)
def current_user(
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
    )
