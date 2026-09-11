"""
Security primitives: password hashing (bcrypt) and the JWT
authentication dependency used to protect routes.

get_current_user is the reusable FastAPI dependency that later
routers (files, dashboard, admin, monitor) will also depend on to
require a valid Bearer token.
"""

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from backend.utils.jwt import decode_access_token

# tokenUrl points Swagger's "Authorize" button at our login endpoint,
# so /docs can obtain and attach a Bearer token automatically.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (includes a random salt)."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a bcrypt hash. Never raises."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    FastAPI dependency: decode the Bearer token and return its claims.

    Raises 401 if the token is missing, malformed, has a bad
    signature, or is expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
    except JWTError:
        raise credentials_exception

    user_id = payload.get("user_id")
    username = payload.get("username")
    role = payload.get("role")

    if user_id is None or username is None or role is None:
        raise credentials_exception

    return {"user_id": user_id, "username": username, "role": role}


def get_current_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    FastAPI dependency: require the caller's JWT to have role='admin'.

    Note: role is read from the JWT claims, not re-checked against the
    DB on every request - if an admin is demoted, their existing
    tokens stay valid (with the old role) until they expire. Fine for
    a short-lived-token prototype; a production system would want a
    revocation/refresh mechanism.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Admin privileges required"
        )
    return current_user
