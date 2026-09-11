"""
PostgreSQL connection handling.

- get_connection() / test_connection(): raw psycopg2 connection + a
  connectivity check (Phase 0).
- init_schema(): creates all tables and seeds storage_nodes using the
  DDL defined in models.py (Phase 1). Idempotent.
"""

import psycopg2
from psycopg2.extensions import connection as PGConnection

from backend.core.config import settings


def get_connection() -> PGConnection:
    """
    Open a new psycopg2 connection using DATABASE_URL from .env.

    Raises psycopg2.OperationalError if the database is unreachable.
    """
    return psycopg2.connect(settings.DATABASE_URL)


def test_connection() -> bool:
    """
    Try to connect to PostgreSQL and run a trivial query.

    Returns True if the database is reachable, False otherwise.
    Never raises - callers use the boolean result to decide what to do.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        conn.close()
        return True
    except Exception as exc:  # noqa: BLE001 - we want to swallow & report
        print(f"[database] Connection test failed: {exc}")
        return False


def init_schema() -> bool:
    """
    Create all tables (if missing) and seed the 3 storage nodes.

    Returns True on success, False if anything failed. Never raises -
    startup should still let the app boot (e.g. so /docs is reachable)
    even if schema init fails; the failure is logged instead.
    """
    # Local import to avoid a circular import at module load time
    # (models.py does not import database.py, but keeping the import
    # here keeps database.py usable standalone for the connection-only
    # use case too).
    from backend.database.models import create_all_tables, seed_storage_nodes

    try:
        conn = get_connection()
        create_all_tables(conn)
        seed_storage_nodes(conn)
        conn.close()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[database] Schema init failed: {exc}")
        return False
