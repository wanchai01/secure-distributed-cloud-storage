"""
File storage service: filename sanitization, size-limited reads,
SHA-256 checksums, storage backend writes, and files-table DB access.

Phase 4 scope: files are always written to storage/node1. Phase 5
replaces the fixed "node1" with real round-robin node selection via
node_service.py - the DB schema and API already support any node
name, so that change won't require touching this file's public shape.

Storage medium (local disk vs Cloudflare R2) is abstracted by
storage_backend.py - added later for cloud deployment, see that
file's docstring and DEPLOYMENT.md.
"""

import hashlib
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from psycopg2.extras import RealDictCursor

from backend.core.config import settings
from backend.database.database import get_connection
from backend.services import storage_backend

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


# ---------------------------------------------------------------------------
# Filename / content safety
# ---------------------------------------------------------------------------


def sanitize_filename(filename: str) -> str:
    """
    Turn a user-supplied filename into a safe display name.

    - Strips any directory components (path traversal defense: "../",
      absolute paths, backslash-style Windows paths all collapse to
      just the base name).
    - Strips null bytes and any character outside [A-Za-z0-9._-].
    - Rejects empty / "." / ".." results.

    NOTE: this sanitized name is stored as `original_filename` for
    display only. The actual stored object key is always a fresh
    server-generated UUID (see generate_stored_filename) - user input
    never reaches the storage backend's key/path.
    """
    if not filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Filename is required")

    name = filename.replace("\x00", "").replace("\\", "/")
    name = name.rsplit("/", 1)[-1]  # keep only the base name

    if name in ("", ".", ".."):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid filename")

    name = _SAFE_FILENAME_RE.sub("_", name)
    return name[:255]


def generate_stored_filename(original_name: str) -> str:
    """Server-generated stored filename: <uuid4><original extension>."""
    ext = Path(original_name).suffix
    if len(ext) > 10:  # implausible extension, likely junk - drop it
        ext = ""
    return f"{uuid.uuid4().hex}{ext}"


async def read_upload_within_limit(
    upload_file: UploadFile, max_bytes: Optional[int] = None
) -> bytes:
    """
    Read an UploadFile into memory in chunks, aborting with 413 the
    moment the configured max size is exceeded (rather than buffering
    an arbitrarily large file first).
    """
    limit = max_bytes if max_bytes is not None else settings.MAX_UPLOAD_SIZE_BYTES
    chunk_size = 1024 * 1024  # 1 MB
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = await upload_file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"File exceeds max upload size of {limit // (1024 * 1024)} MB",
            )
        chunks.append(chunk)

    if total == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")

    return b"".join(chunks)


def compute_checksum(content: bytes) -> str:
    """SHA-256 hex digest, used to detect corruption/tampering later."""
    return hashlib.sha256(content).hexdigest()


def save_file(content: bytes, stored_filename: str, node_name: str) -> str:
    """
    Write bytes under the given node and return the storage key to
    persist in the DB's files.file_path column. Goes to local disk or
    R2 depending on STORAGE_BACKEND - callers don't need to know which.
    """
    key = f"{node_name}/{stored_filename}"
    storage_backend.upload(key, content)
    return key


def delete_file_content(file_path: str) -> None:
    """Best-effort delete of the stored object (disk or R2)."""
    storage_backend.delete(file_path)


def get_file_content(file_path: str) -> bytes:
    """Read a previously-saved file's bytes back. Raises 404 if missing."""
    return storage_backend.download(file_path)


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------


def insert_file_record(
    user_id: int,
    stored_filename: str,
    original_filename: str,
    storage_node: str,
    file_path: str,
    file_size: int,
    mime_type: Optional[str],
    checksum: str,
) -> dict:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO files
                    (user_id, filename, original_filename, storage_node,
                     file_path, file_size, mime_type, checksum)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, filename, original_filename,
                          storage_node, file_size, mime_type, checksum,
                          upload_date;
                """,
                (
                    user_id,
                    stored_filename,
                    original_filename,
                    storage_node,
                    file_path,
                    file_size,
                    mime_type,
                    checksum,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row)
    finally:
        conn.close()


def bump_node_stats(node_name: str, file_delta: int, size_delta: int) -> None:
    """Adjust storage_nodes.total_files / total_size by the given deltas."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE storage_nodes
                SET total_files = total_files + %s,
                    total_size = total_size + %s,
                    updated_at = NOW()
                WHERE node_name = %s;
                """,
                (file_delta, size_delta, node_name),
            )
        conn.commit()
    finally:
        conn.close()


def list_files_for_user(user_id: int) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, user_id, filename, original_filename, storage_node,
                       file_size, mime_type, checksum, upload_date
                FROM files
                WHERE user_id = %s
                ORDER BY upload_date DESC;
                """,
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_file_by_id(file_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, user_id, filename, original_filename, storage_node,
                       file_path, file_size, mime_type, checksum, upload_date
                FROM files
                WHERE id = %s;
                """,
                (file_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def delete_file_record(file_id: int) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM files WHERE id = %s;", (file_id,))
        conn.commit()
    finally:
        conn.close()
