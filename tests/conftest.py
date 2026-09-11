"""
Shared pytest fixtures (Phase 9).

Points the app at a separate test database if TEST_DATABASE_URL is
set (recommended - see README Phase 9), so tests never touch your
real dev data. This override MUST happen before any `backend.*`
module is imported, since backend.core.config reads the environment
once at import time.
"""

import io
import os
import uuid

import pytest

if os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from fastapi.testclient import TestClient  # noqa: E402

from backend.database.database import get_connection, init_schema  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    """Create tables / seed nodes once per test session before any test runs."""
    ok = init_schema()
    assert ok, (
        "Could not initialize the test database schema. Is PostgreSQL "
        "running, and is DATABASE_URL (or TEST_DATABASE_URL) in .env "
        "correct? See README Phase 9."
    )


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def register_user(client):
    """
    Factory fixture: register_user() -> dict with username/password/
    token/user, using a fresh random username each call so tests never
    collide with each other or with previous runs.
    """

    def _register(suffix: str | None = None) -> dict:
        suffix = suffix or uuid.uuid4().hex[:8]
        username = f"testuser_{suffix}"
        email = f"{username}@example.com"
        password = "testpass123"

        r = client.post(
            "/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        assert r.status_code == 201, r.text
        user = r.json()

        r = client.post(
            "/auth/login", data={"username": username, "password": password}
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]

        return {"username": username, "password": password, "token": token, "user": user}

    return _register


@pytest.fixture()
def register_admin(client, register_user):
    """
    Factory fixture: register_admin() -> same shape as register_user(),
    but promoted to role='admin' directly in the DB (mirrors the
    README's manual-promotion instructions), then re-logged-in so the
    token actually carries role=admin.
    """

    def _register_admin(suffix: str | None = None) -> dict:
        u = register_user(suffix)

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET role = 'admin' WHERE username = %s;",
                    (u["username"],),
                )
            conn.commit()
        finally:
            conn.close()

        r = client.post(
            "/auth/login",
            data={"username": u["username"], "password": u["password"]},
        )
        assert r.status_code == 200, r.text
        u["token"] = r.json()["access_token"]
        u["user"]["role"] = "admin"
        return u

    return _register_admin


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_upload(filename: str = "test.txt", content: bytes = b"hello world"):
    """Build a multipart `files=` dict for client.post(..., files=...)."""
    return {"file": (filename, io.BytesIO(content), "text/plain")}


def set_node_status(node_name: str, status_value: str) -> None:
    """Directly flip a storage node's status in the DB (for Phase 5 tests)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE storage_nodes SET status = %s WHERE node_name = %s;",
                (status_value, node_name),
            )
        conn.commit()
    finally:
        conn.close()
