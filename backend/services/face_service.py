"""
OpenCV-based face "authentication" service (Phase 6).

*** PROTOTYPE ONLY - NOT PRODUCTION-GRADE BIOMETRIC SECURITY. ***
Uses Haar-cascade face detection, then a simple holistic appearance
descriptor: the detected face is downsized, blurred, histogram-
equalized, mean-centered, and flattened into a vector - compared by
cosine similarity. This is a classic, easy-to-reason-about baseline
(conceptually similar to pre-deep-learning "Eigenface"-style
appearance matching), built entirely on the approved tech stack
(OpenCV + NumPy - no dlib/face_recognition/opencv-contrib/deep
embedding model).

This demonstrates the register -> verify flow end-to-end for an
educational project. The match threshold below is illustrative, NOT
validated against a real dataset of faces - test it with your own
photos (see README Phase 6) and adjust FACE_VERIFY_THRESHOLD in .env
if you get false accepts/rejects. It has no liveness detection, so it
cannot tell a live face from a printed photo or a video replay. A
real system would use a trained deep embedding model (e.g.
FaceNet/ArcFace), a threshold tuned on labelled data, and liveness
checks. Do not use this to protect anything sensitive.

Flow:
    image bytes -> decode -> Haar cascade face detection ->
    crop/resize/blur/equalize/mean-center -> flatten ("encoding") ->
    save as .npy bytes (register) / compare via cosine similarity (verify)

Encoding storage goes through storage_backend.py (local disk or
Cloudflare R2, depending on STORAGE_BACKEND) rather than writing
directly to disk here.
"""

import io
from typing import Optional

import cv2
import numpy as np
from fastapi import HTTPException, status

from backend.core.config import settings
from backend.database.database import get_connection
from backend.services import storage_backend

FACE_SIZE = (64, 64)  # downsized face crop; smaller = less noise-sensitive

_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------


def _decode_image(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Could not decode image - upload a valid JPEG/PNG",
        )
    return img


def _detect_largest_face(img: np.ndarray) -> tuple[int, int, int, int]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )
    if len(faces) == 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No face detected in the uploaded image",
        )
    # Largest bounding box = most prominent / closest face in frame.
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return int(x), int(y), int(w), int(h)


def compute_encoding(image_bytes: bytes) -> np.ndarray:
    """
    Detect the largest face in the image and return its appearance
    descriptor: downsize -> blur (reduces sensor/JPEG noise
    sensitivity) -> histogram-equalize (reduces lighting sensitivity)
    -> mean-center -> L2-normalize -> flatten.
    """
    img = _decode_image(image_bytes)
    x, y, w, h = _detect_largest_face(img)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_crop = gray[y : y + h, x : x + w]
    face_resized = cv2.resize(face_crop, FACE_SIZE)
    face_blurred = cv2.GaussianBlur(face_resized, (5, 5), 0)
    face_equalized = cv2.equalizeHist(face_blurred)

    vector = face_equalized.astype(np.float32).flatten()
    vector -= vector.mean()  # remove shared brightness/DC bias
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector


def compare_encodings(known: np.ndarray, candidate: np.ndarray) -> float:
    """Cosine similarity between two encodings, roughly in [0, 1] in practice."""
    denom = np.linalg.norm(known) * np.linalg.norm(candidate)
    if denom == 0:
        return 0.0
    return float(np.dot(known, candidate) / denom)


def is_match(confidence: float) -> bool:
    return confidence >= settings.FACE_VERIFY_THRESHOLD


# ---------------------------------------------------------------------------
# Encoding storage (local disk or R2, via storage_backend)
# ---------------------------------------------------------------------------


def save_encoding(user_id: int, encoding: np.ndarray) -> str:
    """Serialize the encoding to .npy bytes and save it. Returns the storage key for the DB."""
    buffer = io.BytesIO()
    np.save(buffer, encoding)
    key = f"faces/user_{user_id}.npy"
    storage_backend.upload(key, buffer.getvalue())
    return key


def load_encoding(face_encoding_path: str) -> np.ndarray:
    content = storage_backend.download(face_encoding_path)
    return np.load(io.BytesIO(content))


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------


def update_user_face_path(user_id: int, path: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET face_encoding_path = %s, updated_at = NOW()
                WHERE id = %s;
                """,
                (path, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_user_face_path(user_id: int) -> Optional[str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT face_encoding_path FROM users WHERE id = %s;", (user_id,)
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def record_face_auth_log(user_id: int, verified: bool, confidence: float) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO face_auth_logs (user_id, verified, confidence)
                VALUES (%s, %s, %s);
                """,
                (user_id, verified, confidence),
            )
        conn.commit()
    finally:
        conn.close()
