"""
Storage backend abstraction: local disk or Cloudflare R2.

Not part of the original Phase 0-9 tech stack - added on request to
solve a real deployment problem: hosts like Render's free tier have
an EPHEMERAL filesystem, so anything written to storage/ locally gets
wiped on every restart/spin-down. R2 (Cloudflare's S3-compatible
object storage, genuinely free up to 10 GB) fixes that.

Selected via STORAGE_BACKEND in .env:
    "local" (default) - writes to storage/<key> on disk, byte-for-byte
        the same behavior as Phases 0-9. Use this for local dev and
        any host with a real persistent filesystem/volume.
    "r2" - writes to a Cloudflare R2 bucket instead. Use this for
        hosts with an ephemeral filesystem. See DEPLOYMENT.md.

file_service.py and face_service.py only call the four functions at
the bottom (upload/download/delete/exists) - they don't know or care
which backend is actually active. `key` is a backend-agnostic path
like "node1/<uuid>.pdf" or "faces/user_5.npy" (no "storage/" prefix -
the local backend adds that internally).
"""

from pathlib import Path

from fastapi import HTTPException, status

from backend.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # .../secure-distributed-cloud-storage
LOCAL_STORAGE_ROOT = PROJECT_ROOT / "storage"


# ---------------------------------------------------------------------------
# Local disk backend (default - identical behavior to Phases 0-9)
# ---------------------------------------------------------------------------


def _local_path(key: str) -> Path:
    """
    Resolve a key to an absolute path under storage/, verifying the
    result is still inside storage/ (defense in depth against a key
    that somehow contains "..").
    """
    dest = (LOCAL_STORAGE_ROOT / key).resolve()
    if LOCAL_STORAGE_ROOT.resolve() not in dest.parents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid storage key")
    return dest


def _local_upload(key: str, content: bytes) -> None:
    dest = _local_path(key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(content)


def _local_download(key: str) -> bytes:
    src = _local_path(key)
    if not src.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found on disk")
    with open(src, "rb") as f:
        return f.read()


def _local_delete(key: str) -> None:
    target = _local_path(key)
    if target.is_file():
        target.unlink()


def _local_exists(key: str) -> bool:
    return _local_path(key).is_file()


# ---------------------------------------------------------------------------
# Cloudflare R2 backend (S3-compatible API, via boto3)
# ---------------------------------------------------------------------------

_r2_client = None


def _get_r2_client():
    global _r2_client
    if _r2_client is None:
        import boto3
        from botocore.client import Config

        _r2_client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    return _r2_client


def _r2_upload(key: str, content: bytes) -> None:
    from botocore.exceptions import ClientError

    try:
        _get_r2_client().put_object(Bucket=settings.R2_BUCKET_NAME, Key=key, Body=content)
    except ClientError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"R2 upload failed: {exc}"
        )


def _r2_download(key: str) -> bytes:
    from botocore.exceptions import ClientError

    try:
        resp = _get_r2_client().get_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
        return resp["Body"].read()
    except ClientError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Object not found in R2")


def _r2_delete(key: str) -> None:
    from botocore.exceptions import ClientError

    try:
        _get_r2_client().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    except ClientError:
        pass  # best-effort, matches the old local-disk delete behavior


def _r2_exists(key: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        _get_r2_client().head_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
        return True
    except ClientError:
        return False


# ---------------------------------------------------------------------------
# Public API - dispatches to whichever backend STORAGE_BACKEND selects
# ---------------------------------------------------------------------------


def upload(key: str, content: bytes) -> None:
    """Write bytes to storage under `key`, creating any needed structure."""
    if settings.STORAGE_BACKEND == "r2":
        _r2_upload(key, content)
    else:
        _local_upload(key, content)


def download(key: str) -> bytes:
    """Read bytes back. Raises 404 if the key doesn't exist."""
    if settings.STORAGE_BACKEND == "r2":
        return _r2_download(key)
    return _local_download(key)


def delete(key: str) -> None:
    """Best-effort delete - never raises if the key is already gone."""
    if settings.STORAGE_BACKEND == "r2":
        _r2_delete(key)
    else:
        _local_delete(key)


def exists(key: str) -> bool:
    if settings.STORAGE_BACKEND == "r2":
        return _r2_exists(key)
    return _local_exists(key)
