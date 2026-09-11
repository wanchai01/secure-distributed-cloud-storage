"""
Auth-related database access.

All queries are parameterized (psycopg2 %s placeholders) - never build
SQL by string-concatenating user input.
"""

from typing import Optional

from psycopg2 import errors
from psycopg2.extras import RealDictCursor

from backend.core.security import hash_password, verify_password
from backend.database.database import get_connection


class DuplicateUserError(Exception):
    """Raised when a username or email is already registered."""


def create_user(username: str, email: str, password: str, role: str = "user") -> dict:
    """Insert a new user with a bcrypt-hashed password. Returns the public fields."""
    password_hash = hash_password(password)
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, username, email, role, created_at, updated_at;
                    """,
                    (username, email, password_hash, role),
                )
                user = cur.fetchone()
                conn.commit()
                return dict(user)
            except errors.UniqueViolation:
                conn.rollback()
                raise DuplicateUserError(
                    "Username or email is already registered"
                )
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[dict]:
    """Fetch a user (including password_hash) by username, or None."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, username, email, password_hash, role,
                       created_at, updated_at
                FROM users
                WHERE username = %s;
                """,
                (username,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Fetch a user's public fields (no password_hash) by id, or None."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, username, email, role, created_at, updated_at
                FROM users
                WHERE id = %s;
                """,
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Return the user dict if username/password are valid, else None."""
    user = get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def record_login_log(
    user_id: Optional[int],
    ip_address: Optional[str],
    status: str,
    face_verified: bool = False,
) -> None:
    """
    Insert one row into login_logs. user_id may be None (e.g. login
    attempt with a username that doesn't exist).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO login_logs (user_id, ip_address, status, face_verified)
                VALUES (%s, %s, %s, %s);
                """,
                (user_id, ip_address, status, face_verified),
            )
        conn.commit()
    finally:
        conn.close()
