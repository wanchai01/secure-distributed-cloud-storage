"""
Database schema (Phase 1).

This project uses raw SQL via psycopg2 (no ORM), so "models" here means:
- DDL statements for every table
- a function to create all tables (idempotent, safe to run on every
  startup thanks to CREATE TABLE IF NOT EXISTS)
- a function to seed the 3 simulated storage nodes

Tables:
    users, files, storage_nodes, login_logs, audit_logs, face_auth_logs
"""

from psycopg2.extensions import connection as PGConnection

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id                  SERIAL PRIMARY KEY,
    username            VARCHAR(50)  NOT NULL UNIQUE,
    email               VARCHAR(255) NOT NULL UNIQUE,
    password_hash       VARCHAR(255) NOT NULL,
    role                VARCHAR(20)  NOT NULL DEFAULT 'user'
                         CHECK (role IN ('user', 'admin')),
    face_encoding_path  VARCHAR(500),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

CREATE_STORAGE_NODES_TABLE = """
CREATE TABLE IF NOT EXISTS storage_nodes (
    id           SERIAL PRIMARY KEY,
    node_name    VARCHAR(50)  NOT NULL UNIQUE,
    node_path    VARCHAR(500) NOT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'online'
                 CHECK (status IN ('online', 'offline')),
    total_files  INTEGER NOT NULL DEFAULT 0,
    total_size   BIGINT  NOT NULL DEFAULT 0,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

CREATE_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS files (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename            VARCHAR(255) NOT NULL,
    original_filename   VARCHAR(255) NOT NULL,
    storage_node        VARCHAR(50)  NOT NULL,
    file_path           VARCHAR(500) NOT NULL,
    file_size           BIGINT NOT NULL,
    mime_type           VARCHAR(100),
    checksum            VARCHAR(64) NOT NULL,
    upload_date         TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

CREATE_FILES_USER_ID_INDEX = """
CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
"""

CREATE_LOGIN_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS login_logs (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ip_address     VARCHAR(45),
    status         VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed')),
    face_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    login_time     TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

CREATE_LOGIN_LOGS_USER_ID_INDEX = """
CREATE INDEX IF NOT EXISTS idx_login_logs_user_id ON login_logs(user_id);
"""

CREATE_AUDIT_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action     VARCHAR(50) NOT NULL,
    target     VARCHAR(255),
    details    TEXT,
    timestamp  TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

CREATE_AUDIT_LOGS_USER_ID_INDEX = """
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
"""

CREATE_FACE_AUTH_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS face_auth_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    verified    BOOLEAN NOT NULL,
    confidence  DOUBLE PRECISION,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

CREATE_FACE_AUTH_LOGS_USER_ID_INDEX = """
CREATE INDEX IF NOT EXISTS idx_face_auth_logs_user_id ON face_auth_logs(user_id);
"""

# Order matters: users first (referenced by files/login_logs/audit_logs/
# face_auth_logs), storage_nodes has no dependency so it can be created
# any time before files.
ALL_TABLE_STATEMENTS = [
    CREATE_USERS_TABLE,
    CREATE_STORAGE_NODES_TABLE,
    CREATE_FILES_TABLE,
    CREATE_FILES_USER_ID_INDEX,
    CREATE_LOGIN_LOGS_TABLE,
    CREATE_LOGIN_LOGS_USER_ID_INDEX,
    CREATE_AUDIT_LOGS_TABLE,
    CREATE_AUDIT_LOGS_USER_ID_INDEX,
    CREATE_FACE_AUTH_LOGS_TABLE,
    CREATE_FACE_AUTH_LOGS_USER_ID_INDEX,
]

# ---------------------------------------------------------------------------
# Table creation / seeding
# ---------------------------------------------------------------------------


def create_all_tables(conn: PGConnection) -> None:
    """
    Create all tables (and indexes) if they do not already exist.

    Idempotent: safe to call on every application startup.
    """
    with conn.cursor() as cur:
        for statement in ALL_TABLE_STATEMENTS:
            cur.execute(statement)
    conn.commit()


def seed_storage_nodes(conn: PGConnection) -> None:
    """
    Ensure the 3 simulated storage nodes (node1, node2, node3) exist
    in the storage_nodes table, pointing at the local storage/ folders
    created in Phase 0. Safe to call multiple times (ON CONFLICT DO
    NOTHING).
    """
    nodes = [
        ("node1", "storage/node1"),
        ("node2", "storage/node2"),
        ("node3", "storage/node3"),
    ]
    with conn.cursor() as cur:
        for node_name, node_path in nodes:
            cur.execute(
                """
                INSERT INTO storage_nodes (node_name, node_path, status)
                VALUES (%s, %s, 'online')
                ON CONFLICT (node_name) DO NOTHING;
                """,
                (node_name, node_path),
            )
    conn.commit()
