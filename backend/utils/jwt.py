"""
JWT helpers.

Encapsulates all JWT creation/decoding so the rest of the app never
touches python-jose directly. Payload always includes user_id,
username, role, and exp (expiry), per the project spec.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import jwt

from backend.core.config import settings


def create_access_token(
    data: dict[str, Any], expires_minutes: Optional[int] = None
) -> str:
    """
    Build a signed JWT.

    `data` should contain at least user_id, username, role - `exp` is
    added automatically and will overwrite any "exp" key passed in.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT (signature + expiry).

    Raises jose.JWTError on any failure - invalid signature, malformed
    token, or expired token (jose.ExpiredSignatureError is a subclass
    of JWTError). Callers should catch JWTError and turn it into a 401.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
