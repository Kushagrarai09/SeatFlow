"""Registration, login, refresh, logout, and current-user endpoints."""

import hashlib
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    _decode_token,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import RefreshToken, User
from app.schemas_auth import AuthTokens, LoginRequest, RefreshRequest, RegisterRequest, UserRead

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
DbSession = Annotated[Session, Depends(get_db)]


def _token_digest(token_id: str) -> str:
    return hashlib.sha256(token_id.encode("utf-8")).hexdigest()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> User:
    """Create an attendee account; callers cannot self-assign privileged roles."""
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role="attendee",
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    db.refresh(user)
    return user


@router.post("/login", response_model=AuthTokens)
def login(payload: LoginRequest, db: DbSession) -> AuthTokens:
    """Verify credentials and issue access and refresh tokens."""
    user = db.scalar(select(User).where(User.email == str(payload.email).strip().lower()))
    if user is None or not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    refresh_token, token_id, expires_at = create_refresh_token(user)
    db.add(RefreshToken(
        user_id=user.id,
        token_digest=_token_digest(token_id),
        expires_at=expires_at.replace(tzinfo=None),
    ))
    db.commit()
    return AuthTokens(access_token=create_access_token(user), refresh_token=refresh_token)


@router.post("/refresh", response_model=AuthTokens)
def refresh_tokens(payload: RefreshRequest, db: DbSession) -> AuthTokens:
    """Rotate a refresh token; a previously consumed token cannot be reused."""
    decoded = _decode_token(payload.refresh_token, "refresh")
    try:
        user_id = int(decoded["sub"])
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    token_id = str(decoded["jti"])
    user = db.get(User, user_id)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Conditional UPDATE makes single-use token consumption atomic under concurrent refresh requests.
    consumed = db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_digest == _token_digest(token_id),
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .values(revoked_at=now)
    )
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    replacement, replacement_id, expires_at = create_refresh_token(user)
    db.add(RefreshToken(
        user_id=user.id,
        token_digest=_token_digest(replacement_id),
        expires_at=expires_at.replace(tzinfo=None),
    ))
    db.commit()
    return AuthTokens(access_token=create_access_token(user), refresh_token=replacement)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshRequest,
    db: DbSession,
    current_user: User = Depends(get_current_user),
) -> None:
    """Revoke the caller's refresh token. Access tokens expire within 30 minutes."""
    decoded = _decode_token(payload.refresh_token, "refresh")
    if str(decoded.get("sub")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Refresh token does not belong to current user")
    record = db.scalar(select(RefreshToken).where(
        RefreshToken.token_digest == _token_digest(str(decoded["jti"]))
    ))
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user's safe profile."""
    return current_user
