"""
Distributed storage node service (Phase 5).

Simulates distributed storage using local folders (storage/node1,
storage/node2, storage/node3) that were created in Phase 0 and seeded
into the storage_nodes table in Phase 1. Node selection is simple
round-robin among currently "online" nodes.

This is a prototype: no real network distribution, no replication,
no consensus. It only demonstrates the selection/bookkeeping pattern
that a real distributed storage layer would need.
"""

from typing import Optional

from fastapi import HTTPException, status
from psycopg2.extras import RealDictCursor

from backend.database.database import get_connection


def get_all_nodes() -> list[dict]:
    """Full node list with status and usage stats, ordered by name."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, node_name, node_path, status, total_files,
                       total_size, created_at, updated_at
                FROM storage_nodes
                ORDER BY node_name;
                """
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_online_node_names() -> list[str]:
    """Names of nodes currently marked 'online', ordered by name."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT node_name
                FROM storage_nodes
                WHERE status = 'online'
                ORDER BY node_name;
                """
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def _get_total_file_count() -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM files;")
            return cur.fetchone()[0]
    finally:
        conn.close()


def select_node() -> str:
    """
    Pick the node for the next upload: round-robin over the online
    nodes, keyed off how many files already exist
    (total_files_so_far % number_of_online_nodes). With 3 online nodes
    this gives node1 -> node2 -> node3 -> node1 -> ...

    Raises 503 if no nodes are online (nothing to write to).
    """
    online = get_online_node_names()
    if not online:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "No storage nodes are currently online",
        )
    count = _get_total_file_count()
    index = count % len(online)
    return online[index]


def set_node_status(node_name: str, status_value: str) -> Optional[dict]:
    """
    Mark a node online/offline. Not exposed via an API route yet (that
    comes with Phase 7's admin endpoints) - useful for manually testing
    failover in the meantime via direct SQL, or by importing this
    function in a Python shell.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE storage_nodes
                SET status = %s, updated_at = NOW()
                WHERE node_name = %s
                RETURNING id, node_name, node_path, status, total_files, total_size;
                """,
                (status_value, node_name),
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
    finally:
        conn.close()
