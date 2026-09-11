"""
Admin routes (Phase 7 + Phase 8): system-wide listings, admin-only.

Every route requires get_current_admin_user (role='admin' in the
JWT) - a regular user gets 403. No dedicated admin_service.py per the
project's services/ layout (auth/file/face/node/notification only);
these are read-only listings, so the queries live directly in the
router, same pattern as dashboard.py. node_service is reused for
/admin/nodes since it already has the right query.

Each route depends on get_current_admin_user directly (rather than a
router-level dependency) so it can also record who viewed what via
notification_service.notify(..., "ADMIN_ACTION", ...) - Phase 8's
audit-logging wiring.

All list endpoints accept an optional `limit` (default 100, max 500)
to avoid accidentally pulling an unbounded result set.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from backend.core.security import get_current_admin_user
from backend.database.database import get_connection
from backend.services import node_service
from backend.services.notification_service import notify

router = APIRouter(prefix="/admin", tags=["Admin"])

LimitQuery = Query(default=100, ge=1, le=500)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AdminUser(BaseModel):
    id: int
    username: str
    email: str
    role: str
    created_at: datetime
    updated_at: datetime


class AdminFile(BaseModel):
    id: int
    user_id: int
    username: Optional[str] = None
    filename: str
    original_filename: str
    storage_node: str
    file_size: int
    mime_type: Optional[str] = None
    checksum: str
    upload_date: datetime


class LoginLogEntry(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    ip_address: Optional[str] = None
    status: str
    face_verified: bool
    login_time: datetime


class AuditLogEntry(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    target: Optional[str] = None
    details: Optional[str] = None
    timestamp: datetime


class NodeInfo(BaseModel):
    id: int
    node_name: str
    node_path: str
    status: str
    total_files: int
    total_size: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[AdminUser], summary="List all users")
def list_users(
    limit: int = LimitQuery,
    current_admin: dict = Depends(get_current_admin_user),
):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, username, email, role, created_at, updated_at
                FROM users
                ORDER BY id
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    notify(
        current_admin["user_id"], current_admin["username"], "ADMIN_ACTION",
        target="viewed /admin/users",
    )
    return rows


@router.get("/files", response_model=list[AdminFile], summary="List all files")
def list_files(
    limit: int = LimitQuery,
    current_admin: dict = Depends(get_current_admin_user),
):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT f.id, f.user_id, u.username, f.filename,
                       f.original_filename, f.storage_node, f.file_size,
                       f.mime_type, f.checksum, f.upload_date
                FROM files f
                LEFT JOIN users u ON u.id = f.user_id
                ORDER BY f.upload_date DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    notify(
        current_admin["user_id"], current_admin["username"], "ADMIN_ACTION",
        target="viewed /admin/files",
    )
    return rows


@router.get(
    "/logins", response_model=list[LoginLogEntry], summary="List login attempts"
)
def list_logins(
    limit: int = LimitQuery,
    current_admin: dict = Depends(get_current_admin_user),
):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT l.id, l.user_id, u.username, l.ip_address, l.status,
                       l.face_verified, l.login_time
                FROM login_logs l
                LEFT JOIN users u ON u.id = l.user_id
                ORDER BY l.login_time DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    notify(
        current_admin["user_id"], current_admin["username"], "ADMIN_ACTION",
        target="viewed /admin/logins",
    )
    return rows


@router.get(
    "/audit-logs",
    response_model=list[AuditLogEntry],
    summary="List audit log entries",
)
def list_audit_logs(
    limit: int = LimitQuery,
    current_admin: dict = Depends(get_current_admin_user),
):
    """
    Populated from Phase 8 onward - every notify() call across the app
    (register/login/upload/download/delete/face register+verify/admin
    actions) writes a row here via notification_service.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.id, a.user_id, u.username, a.action, a.target,
                       a.details, a.timestamp
                FROM audit_logs a
                LEFT JOIN users u ON u.id = a.user_id
                ORDER BY a.timestamp DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    notify(
        current_admin["user_id"], current_admin["username"], "ADMIN_ACTION",
        target="viewed /admin/audit-logs",
    )
    return rows


@router.get("/nodes", response_model=list[NodeInfo], summary="List storage nodes")
def list_nodes(current_admin: dict = Depends(get_current_admin_user)):
    nodes = node_service.get_all_nodes()
    notify(
        current_admin["user_id"], current_admin["username"], "ADMIN_ACTION",
        target="viewed /admin/nodes",
    )
    return nodes
