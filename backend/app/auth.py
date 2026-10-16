"""Authentication primitives and dependencies for SeatFlow."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"
_ACCESS_TOKEN_MINUTES = 30
_REFRESH_TOKEN_DAYS = 14
_PBKDF2_ITERATIONS = 310_000


def _secret_key() -> str:
    value = os.getenv("JWT_SECRET_KEY", "").strip()
    if len(value) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters")
    return value


def hash_password(password: str) -> str:
    """Hash a password with salted PBKDF2-HMAC-SHA256."""
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must contain between 8 and 128 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return "pbkdf2_sha256$" + str(_PBKDF2_ITERATIONS) + "$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, encoded: str) -> bool:
    """Verify a stored salted password hash without leaking comparison timing."""
    try:
        algorithm, iterations_text, salt_hex, digest_hex = encoded.split("$", 3)
        iterations = int(iterations_text)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations)
        return hmac.compare_digest(actual, bytes.fromhex(digest_hex))
    except (ValueError, TypeError):
        return False


def _sign_token(payload: dict[str, object]) -> str:
    """Sign a JWT with the configured application secret."""
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def _decode_token(token: str, expected_type: str) -> dict[str, object]:
    """Verify signature, standard claims, expiry, and application-specific token type."""
    try:
        payload = jwt.decode(
            token,
            _secret_key(),
            algorithms=[ALGORITHM],
            options={"require": ["exp", "iat", "sub", "jti", "typ"]},
        )
        if not isinstance(payload, dict) or payload.get("typ") != expected_type:
            raise InvalidTokenError("wrong token type")
        if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("jti"), str):
            raise InvalidTokenError("invalid token subject or identifier")
        return payload
    except (InvalidTokenError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return _sign_token({
        "sub": str(user.id),
        "role": user.role,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=_ACCESS_TOKEN_MINUTES),
        "jti": secrets.token_urlsafe(16),
    })


def create_refresh_token(user: User) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    token_id = secrets.token_urlsafe(24)
    expires_at = now + timedelta(days=_REFRESH_TOKEN_DAYS)
    token = _sign_token({
        "sub": str(user.id),
        "typ": "refresh",
        "iat": now,
        "exp": expires_at,
        "jti": token_id,
    })
    return token, token_id, expires_at


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    payload = _decode_token(credentials.credentials, "access")
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise HTTPException(401, "Invalid or expired token") from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Invalid or expired token")
    return user


def require_roles(*roles: str):
    """Build a FastAPI dependency allowing only the selected account roles."""
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return dependency



def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Return None for anonymous requests, but validate any supplied bearer token."""
    if credentials is None:
        return None
    payload = _decode_token(credentials.credentials, "access")
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user
