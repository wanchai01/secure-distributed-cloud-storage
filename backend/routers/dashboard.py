"""
Dashboard route: aggregate stats about the system.

No dedicated dashboard_service.py per the project's services/ layout
(auth_service, file_service, face_service, node_service,
notification_service) - this is a read-only aggregation endpoint, so
the queries live directly in the router. Requires a valid JWT (any
role) since user/file counts are internal information, not public.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from backend.core.security import get_current_user
from backend.database.database import get_connection

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class NodeStatus(BaseModel):
    node_name: str
    status: str
    total_files: int
    total_size: int


class DashboardResponse(BaseModel):
    users: int
    files: int
    storage_used: int
    nodes: int
    online_nodes: int
    login_count: int
    node_status: list[NodeStatus]


@router.get("", response_model=DashboardResponse, summary="System-wide stats")
def get_dashboard(current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS count FROM users;")
            users_count = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) AS count FROM files;")
            files_count = cur.fetchone()["count"]

            cur.execute(
                "SELECT COALESCE(SUM(file_size), 0) AS total FROM files;"
            )
            storage_used = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS count FROM storage_nodes;")
            nodes_count = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM storage_nodes WHERE status = 'online';"
            )
            online_nodes_count = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) AS count FROM login_logs WHERE status = 'success';"
            )
            login_count = cur.fetchone()["count"]

            cur.execute(
                """
                SELECT node_name, status, total_files, total_size
                FROM storage_nodes
                ORDER BY node_name;
                """
            )
            node_status = cur.fetchall()

        return DashboardResponse(
            users=users_count,
            files=files_count,
            storage_used=storage_used,
            nodes=nodes_count,
            online_nodes=online_nodes_count,
            login_count=login_count,
            node_status=[NodeStatus(**row) for row in node_status],
        )
    finally:
        conn.close()
