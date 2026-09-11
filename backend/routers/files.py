"""
File routes: upload, list, get metadata, download, delete.

Every route requires a valid JWT. Ownership is enforced on every
per-file route: a user may only see/download/delete their own files
(403 if the file belongs to someone else, 404 if it doesn't exist at
all). storage_node is chosen per-upload by node_service's round-robin
selection across node1/node2/node3 (Phase 5).
"""

from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel

from backend.core.security import get_current_user
from backend.services import file_service, node_service
from backend.services.notification_service import notify

router = APIRouter(prefix="/files", tags=["Files"])


class FileMetadata(BaseModel):
    id: int
    user_id: int
    filename: str
    original_filename: str
    storage_node: str
    file_size: int
    mime_type: Optional[str] = None
    checksum: str
    upload_date: datetime


def _get_owned_file_or_error(file_id: int, current_user: dict) -> dict:
    """Fetch a file row, raising 404 (not found) or 403 (not the owner)."""
    file_row = file_service.get_file_by_id(file_id)
    if not file_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    if file_row["user_id"] != current_user["user_id"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not have access to this file"
        )
    return file_row


@router.post(
    "/upload",
    response_model=FileMetadata,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file",
)
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    original_name = file_service.sanitize_filename(file.filename or "")
    content = await file_service.read_upload_within_limit(file)
    checksum = file_service.compute_checksum(content)
    stored_filename = file_service.generate_stored_filename(original_name)

    # Round-robin across online nodes; raises 503 if none are online.
    storage_node = node_service.select_node()

    file_path = file_service.save_file(content, stored_filename, storage_node)

    record = file_service.insert_file_record(
        user_id=current_user["user_id"],
        stored_filename=stored_filename,
        original_filename=original_name,
        storage_node=storage_node,
        file_path=file_path,
        file_size=len(content),
        mime_type=file.content_type,
        checksum=checksum,
    )
    file_service.bump_node_stats(
        storage_node, file_delta=1, size_delta=len(content)
    )
    notify(
        current_user["user_id"],
        current_user["username"],
        "UPLOAD",
        target=original_name,
        details=f"size={len(content)} node={storage_node}",
    )
    return record


@router.get("", response_model=list[FileMetadata], summary="List my files")
def list_files(current_user: dict = Depends(get_current_user)):
    return file_service.list_files_for_user(current_user["user_id"])


@router.get("/{file_id}", response_model=FileMetadata, summary="Get file metadata")
def get_file_metadata(file_id: int, current_user: dict = Depends(get_current_user)):
    return _get_owned_file_or_error(file_id, current_user)


@router.get("/{file_id}/download", summary="Download a file")
def download_file(file_id: int, current_user: dict = Depends(get_current_user)):
    file_row = _get_owned_file_or_error(file_id, current_user)
    content = file_service.get_file_content(file_row["file_path"])

    notify(
        current_user["user_id"],
        current_user["username"],
        "DOWNLOAD",
        target=file_row["original_filename"],
    )

    # RFC 5987 filename* so non-ASCII original filenames still work.
    safe_name = quote(file_row["original_filename"])
    return Response(
        content=content,
        media_type=file_row["mime_type"] or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}"
        },
    )


@router.delete(
    "/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a file"
)
def delete_file(file_id: int, current_user: dict = Depends(get_current_user)):
    file_row = _get_owned_file_or_error(file_id, current_user)

    file_service.delete_file_content(file_row["file_path"])
    file_service.delete_file_record(file_id)
    file_service.bump_node_stats(
        file_row["storage_node"],
        file_delta=-1,
        size_delta=-file_row["file_size"],
    )
    notify(
        current_user["user_id"],
        current_user["username"],
        "DELETE",
        target=file_row["original_filename"],
    )
    return None
