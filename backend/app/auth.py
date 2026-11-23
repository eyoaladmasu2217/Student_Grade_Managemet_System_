import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.audit import log_security_event
from app.config import use_secure_cookies
from app.database import get_db
from app.login_guard import login_throttle
from app.password_policy import validate_password
from app.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    verify_login_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
SESSION_COOKIE = "sgms_session"
SESSION_DURATION = timedelta(hours=12)
SESSION_IDLE_TIMEOUT = timedelta(hours=2)


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=use_secure_cookies(),
        samesite="lax",
        max_age=int(SESSION_DURATION.total_seconds()),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=use_secure_cookies(),
        samesite="lax",
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password_strength(cls, value: str) -> str:
        return validate_password(value)


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool = True


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
               sessions.id AS session_id, sessions.expires_at, sessions.last_seen_at
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ?
        """,
        (hash_session_token(token),),
    ).fetchone()
    if row is None or not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid")

    now = datetime.now(timezone.utc)
    expiry = parse_timestamp(row["expires_at"])
    last_seen = parse_timestamp(row["last_seen_at"]) if row["last_seen_at"] else now
    expired = expiry <= now or now - last_seen > SESSION_IDLE_TIMEOUT
    if expired:
        connection.execute("DELETE FROM sessions WHERE id = ?", (row["session_id"],))
        connection.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired")

    connection.execute(
        "UPDATE sessions SET last_seen_at = ? WHERE id = ?",
        (now.isoformat(), row["session_id"]),
    )
    connection.commit()
    return row


def require_roles(*roles: str):
    def role_guard(
        user: Annotated[sqlite3.Row, Depends(get_current_user)],
    ) -> sqlite3.Row:
        if user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return role_guard


def client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> UserResponse:
    email = str(payload.email)
    address = client_address(request)
    retry_after = login_throttle.retry_after(email, address)
    if retry_after is not None:
        log_security_event("login", "failure", email=email, address=address, reason="throttled")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = connection.execute(
        "SELECT id, email, full_name, password_hash, role, is_active FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    stored_hash = user["password_hash"] if user is not None and user["is_active"] else None
    password_is_valid = verify_login_password(payload.password, stored_hash)
    if user is None or not user["is_active"] or not password_is_valid:
        login_throttle.record_failure(email, address)
        log_security_event(
            "login", "failure", email=email, address=address, reason="invalid_credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
        )

    login_throttle.clear(email, address)
    log_security_event(
        "login", "success", email=email, user_id=user["id"], address=address
    )
    token = create_session_token()
    expires_at = datetime.now(timezone.utc) + SESSION_DURATION
    connection.execute(
        """
        INSERT INTO sessions (user_id, token_hash, expires_at, last_seen_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            user["id"],
            hash_session_token(token),
            expires_at.isoformat(),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    connection.commit()
    set_session_cookie(response, token)
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        is_active=bool(user["is_active"]),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
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
    log_security_event("logout", "success")
    clear_session_cookie(response)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def logout_all_sessions(
    response: Response,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> None:
    connection.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    connection.commit()
    log_security_event("logout_all", "success", user_id=user["id"])
    clear_session_cookie(response)


@router.get("/me", response_model=UserResponse)
def current_user(
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        is_active=bool(user["is_active"]),
    )


@router.post("/change-password", response_model=UserResponse)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    user: Annotated[sqlite3.Row, Depends(get_current_user)],
    connection: Annotated[sqlite3.Connection, Depends(get_db)],
) -> UserResponse:
    connection.execute("BEGIN IMMEDIATE")
    account = connection.execute(
        "SELECT password_hash FROM users WHERE id = ? AND is_active = 1",
        (user["id"],),
    ).fetchone()
    if account is None or not verify_password(
        payload.current_password, account["password_hash"]
    ):
        log_security_event("password_change", "failure", user_id=user["id"], reason="bad_current")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if verify_password(payload.new_password, account["password_hash"]):
        log_security_event("password_change", "failure", user_id=user["id"], reason="reused")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be different from the current password",
        )
    try:
        validate_password(payload.new_password, user["email"])
    except ValueError as error:
        log_security_event("password_change", "failure", user_id=user["id"], reason="weak")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error

    token = create_session_token()
    expires_at = datetime.now(timezone.utc) + SESSION_DURATION
    connection.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(payload.new_password), user["id"]),
    )
    connection.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    log_security_event("password_change", "success", user_id=user["id"])
    connection.execute(
        """
        INSERT INTO sessions (user_id, token_hash, expires_at, last_seen_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            user["id"],
            hash_session_token(token),
            expires_at.isoformat(),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    connection.commit()
    set_session_cookie(response, token)
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        is_active=bool(user["is_active"]),
    )
