"""
Face authentication routes (Phase 6).

*** PROTOTYPE - see backend/services/face_service.py docstring for
details. Not a production biometric security system. ***

- POST /face/register - upload a photo; detect + store a face
  "encoding" for the current user.
- POST /face/verify - upload a photo; compare it against the current
  user's stored encoding and log the attempt to face_auth_logs.
- POST /face/login - log in with a username + photo instead of a
  password. Added on request to let the console actually offer "sign
  in with your face" rather than only verifying an already-logged-in
  session. Still 1:1 (username picks whose encoding to compare
  against), not 1:N face search - that keeps the same cosine-
  similarity comparison /face/verify already uses, just gated by
  username instead of a JWT. Same prototype caveats apply: no
  liveness detection, illustrative threshold. Do not use this to
  protect anything sensitive.

/face/register and /face/verify require a valid JWT (a user can only
register/verify their own face - there's no "verify as someone else"
option there). /face/login is intentionally unauthenticated - it's an
alternative to /auth/login, so by definition runs before any JWT
exists. The actual camera capture happens client-side (browser/app);
this backend only ever receives an already-captured image file.
"""

from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel

from backend.core.security import get_current_user
from backend.routers.auth import TokenResponse
from backend.services import auth_service, face_service
from backend.services.notification_service import notify
from backend.utils.jwt import create_access_token

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


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in with a username + face photo instead of a password",
)
async def face_login(
    request: Request,
    username: str = Form(...),
    file: UploadFile = File(...),
):
    client_ip = request.client.host if request.client else None
    content = await _read_image(file)
    user = auth_service.get_user_by_username(username)

    # Same response either way (unknown username / no face registered /
    # no match) so a failed attempt can't be used to enumerate which
    # usernames exist or which users have face auth set up - mirrors
    # how /auth/login always says "Incorrect username or password".
    def reject(user_id: Optional[int]) -> HTTPException:
        auth_service.record_login_log(
            user_id=user_id, ip_address=client_ip, status="failed", face_verified=True
        )
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Face not recognized for this username",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user:
        raise reject(None)

    stored_path = face_service.get_user_face_path(user["id"])
    if not stored_path:
        raise reject(user["id"])

    known_encoding = face_service.load_encoding(stored_path)
    candidate_encoding = face_service.compute_encoding(content)  # 400 if no face
    similarity = face_service.compare_encodings(known_encoding, candidate_encoding)
    verified = face_service.is_match(similarity)

    face_service.record_face_auth_log(
        user_id=user["id"], verified=verified, confidence=similarity
    )
    if not verified:
        raise reject(user["id"])

    auth_service.record_login_log(
        user_id=user["id"], ip_address=client_ip, status="success", face_verified=True
    )
    notify(
        user["id"],
        user["username"],
        "LOGIN",
        details=f"ip={client_ip} face_verified=True confidence={round(similarity, 4)}",
    )

    access_token = create_access_token(
        {"user_id": user["id"], "username": user["username"], "role": user["role"]}
    )
    return TokenResponse(access_token=access_token)
