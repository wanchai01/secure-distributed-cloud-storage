"""
Face authentication routes (Phase 6).

*** PROTOTYPE - see backend/services/face_service.py docstring for
details. Not a production biometric security system. ***

- POST /face/register - upload a photo; detect + store a face
  "encoding" for the current user.
- POST /face/verify - upload a photo; compare it against the current
  user's stored encoding and log the attempt to face_auth_logs.

Both routes require a valid JWT (a user can only register/verify
their own face - there's no "verify as someone else" option here).
The actual camera capture happens client-side (browser/app); this
backend only ever receives an already-captured image file.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.core.security import get_current_user
from backend.services import face_service
from backend.services.notification_service import notify

router = APIRouter(prefix="/face", tags=["Face Authentication"])

MAX_IMAGE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB - generous for one photo


class FaceRegisterResponse(BaseModel):
    message: str
    face_encoding_path: str


class FaceVerifyResponse(BaseModel):
    verified: bool
    confidence: float


async def _read_image(file: UploadFile) -> bytes:
    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded image is empty")
    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Image exceeds max size of {MAX_IMAGE_SIZE_BYTES // (1024 * 1024)} MB",
        )
    return content


@router.post(
    "/register", response_model=FaceRegisterResponse, summary="Register your face"
)
async def register_face(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    content = await _read_image(file)
    encoding = face_service.compute_encoding(content)  # 400 if no face detected
    path = face_service.save_encoding(current_user["user_id"], encoding)
    face_service.update_user_face_path(current_user["user_id"], path)

    notify(current_user["user_id"], current_user["username"], "FACE_REGISTER")

    return FaceRegisterResponse(
        message="Face registered successfully", face_encoding_path=path
    )


@router.post(
    "/verify", response_model=FaceVerifyResponse, summary="Verify your face"
)
async def verify_face(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    content = await _read_image(file)

    stored_path = face_service.get_user_face_path(current_user["user_id"])
    if not stored_path:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No face registered for this user - call /face/register first",
        )

    known_encoding = face_service.load_encoding(stored_path)
    candidate_encoding = face_service.compute_encoding(content)  # 400 if no face

    similarity = face_service.compare_encodings(known_encoding, candidate_encoding)
    verified = face_service.is_match(similarity)

    face_service.record_face_auth_log(
        user_id=current_user["user_id"], verified=verified, confidence=similarity
    )
    notify(
        current_user["user_id"],
        current_user["username"],
        "FACE_VERIFY",
        details=f"verified={verified} confidence={round(similarity, 4)}",
    )

    return FaceVerifyResponse(verified=verified, confidence=round(similarity, 4))
