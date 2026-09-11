"""
End-to-end demo walkthrough.

Exercises every phase of the API against a REAL running server + REAL
PostgreSQL - not a mock. Uses only stdlib (urllib) for HTTP calls and
psycopg2 (already a project dependency) to promote a demo user to
admin directly in the DB, the same way the README's manual Phase 7
instructions do.

Usage:
    1. Start the server first:  uvicorn backend.main:app --reload
    2. In another terminal:      python demo.py

Optional: set DEMO_BASE_URL to point at a non-default host/port
(default http://127.0.0.1:8000).
"""

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlencode

BASE_URL = os.getenv("DEMO_BASE_URL", "http://127.0.0.1:8000")


# ---------------------------------------------------------------------------
# Tiny HTTP helper (stdlib only - no extra dependency needed for the demo)
# ---------------------------------------------------------------------------


def _request(method, path, token=None, json_body=None, form_body=None, files=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif form_body is not None:
        data = urlencode(form_body).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif files is not None:
        boundary = uuid.uuid4().hex
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        parts = []
        for field_name, (filename, content, content_type) in files.items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{filename}"\r\n'.encode()
            )
            parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
            parts.append(content)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        data = b"".join(parts)

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else None), body
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body), body
        except json.JSONDecodeError:
            return e.code, None, body
    except urllib.error.URLError as e:
        print(f"\n[FATAL] Could not reach {url}")
        print(f"        {e}")
        print("        Is the server running? Start it with:")
        print("        uvicorn backend.main:app --reload")
        sys.exit(1)


def step(title):
    print(f"\n{'=' * 70}\n  {title}\n{'=' * 70}")


def show(method, path, status, body):
    ok = "OK " if 200 <= status < 300 else "!! "
    print(f"{ok}{method} {path} -> {status}")
    if body is not None:
        preview = json.dumps(body, indent=2, default=str)
        if len(preview) > 800:
            preview = preview[:800] + "\n  ... (truncated)"
        print(preview)


# ---------------------------------------------------------------------------
# Synthetic "face" image generator (Phase 6 demo, no webcam needed)
# ---------------------------------------------------------------------------


def _make_synthetic_face_jpeg(seed: int) -> bytes:
    """
    Draws a simple face-like pattern (oval + eyes + nose + mouth) that
    OpenCV's Haar cascade can actually detect, so /face/register and
    /face/verify can be demoed without a real webcam photo. This is
    purely a demo convenience, not something the app relies on.
    """
    import cv2
    import numpy as np

    rng = np.random.default_rng(seed)
    img = np.full((300, 300, 3), 200, dtype=np.uint8)
    cv2.ellipse(img, (150, 150), (100, 130), 0, 0, 360, (180, 170, 160), -1)
    eye_offset = int(rng.integers(-5, 5))
    cv2.circle(img, (110 + eye_offset, 120), 15, (50, 50, 50), -1)
    cv2.circle(img, (190 + eye_offset, 120), 15, (50, 50, 50), -1)
    cv2.line(img, (150, 130), (150, 170), (100, 90, 90), 3)
    cv2.ellipse(img, (150, 210), (40, 15), 0, 0, 180, (80, 60, 60), 3)
    ok, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


# ---------------------------------------------------------------------------
# Demo script
# ---------------------------------------------------------------------------


def main():
    suffix = uuid.uuid4().hex[:8]
    username = f"demo_{suffix}"
    email = f"{username}@example.com"
    password = "demopass123"

    print(f"Demo run against {BASE_URL}")
    print(f"Demo user: {username}")

    # --- Phase 8: public health check (no auth needed) ------------------
    step("Phase 8 - GET /monitor/health (public, no auth)")
    status, body, _ = _request("GET", "/monitor/health")
    show("GET", "/monitor/health", status, body)

    # --- Phase 2: register + login ---------------------------------------
    step("Phase 2 - POST /auth/register")
    status, body, _ = _request(
        "POST",
        "/auth/register",
        json_body={"username": username, "email": email, "password": password},
    )
    show("POST", "/auth/register", status, body)
    assert status == 201, "Register failed - stopping demo"

    step("Phase 2 - POST /auth/login")
    status, body, _ = _request(
        "POST", "/auth/login", form_body={"username": username, "password": password}
    )
    show("POST", "/auth/login", status, body)
    assert status == 200, "Login failed - stopping demo"
    token = body["access_token"]

    step("Phase 2 - GET /auth/me")
    status, body, _ = _request("GET", "/auth/me", token=token)
    show("GET", "/auth/me", status, body)

    # --- Phase 3: dashboard ------------------------------------------------
    step("Phase 3 - GET /dashboard")
    status, body, _ = _request("GET", "/dashboard", token=token)
    show("GET", "/dashboard", status, body)

    # --- Phase 4/5: file upload/list/get/download/delete -------------------
    step("Phase 4/5 - POST /files/upload")
    file_content = b"Hello from the demo script! This is a test file.\n"
    status, body, _ = _request(
        "POST",
        "/files/upload",
        token=token,
        files={"file": ("demo.txt", file_content, "text/plain")},
    )
    show("POST", "/files/upload", status, body)
    assert status == 201, "Upload failed - stopping demo"
    file_id = body["id"]
    print(f"  -> stored on: {body['storage_node']} (round-robin selection, Phase 5)")

    step("Phase 4 - GET /files (list)")
    status, body, _ = _request("GET", "/files", token=token)
    show("GET", "/files", status, body)

    step("Phase 4 - GET /files/{id}/download")
    status, _, raw = _request("GET", f"/files/{file_id}/download", token=token)
    ok = "OK " if status == 200 else "!! "
    print(f"{ok}GET /files/{file_id}/download -> {status}")
    print(f"  content matches upload: {raw == file_content}")

    # --- Phase 6: face register/verify (synthetic images) -------------------
    step("Phase 6 - POST /face/register (synthetic demo photo)")
    face_a = _make_synthetic_face_jpeg(seed=1)
    status, body, _ = _request(
        "POST",
        "/face/register",
        token=token,
        files={"file": ("face.jpg", face_a, "image/jpeg")},
    )
    show("POST", "/face/register", status, body)

    if status == 201 or status == 200:
        step("Phase 6 - POST /face/verify (same synthetic photo)")
        status, body, _ = _request(
            "POST",
            "/face/verify",
            token=token,
            files={"file": ("face.jpg", face_a, "image/jpeg")},
        )
        show("POST", "/face/verify", status, body)

        step("Phase 6 - POST /face/verify (different synthetic photo)")
        face_b = _make_synthetic_face_jpeg(seed=99)
        status, body, _ = _request(
            "POST",
            "/face/verify",
            token=token,
            files={"file": ("face2.jpg", face_b, "image/jpeg")},
        )
        show("POST", "/face/verify", status, body)
    else:
        print("  (skipping verify steps - register did not return 200/201)")

    step("Phase 4 - DELETE /files/{id}")
    status, body, _ = _request("DELETE", f"/files/{file_id}", token=token)
    print(f"{'OK ' if status == 204 else '!! '}DELETE /files/{file_id} -> {status}")

    # --- Phase 7/8: promote to admin, hit admin + monitor endpoints --------
    step("Phase 7 - promoting demo user to admin (direct SQL, like the README)")
    try:
        from dotenv import load_dotenv

        load_dotenv()
        import psycopg2

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET role = 'admin' WHERE username = %s;", (username,)
            )
        conn.commit()
        conn.close()
        print("  users.role updated to 'admin' in the DB")
    except Exception as e:
        print(f"  [SKIPPED] could not promote via direct DB access: {e}")
        print("  (admin endpoints below will show 403 - that's expected)")

    step("Phase 2 - re-login to get a fresh admin-role token")
    status, body, _ = _request(
        "POST", "/auth/login", form_body={"username": username, "password": password}
    )
    show("POST", "/auth/login", status, body)
    token = body["access_token"]

    for path in ("/admin/users", "/admin/files", "/admin/nodes", "/admin/logins", "/admin/audit-logs"):
        step(f"Phase 7 - GET {path}")
        status, body, _ = _request("GET", path, token=token)
        show("GET", path, status, body)

    step("Phase 8 - GET /monitor/nodes")
    status, body, _ = _request("GET", "/monitor/nodes")
    show("GET", "/monitor/nodes", status, body)

    print(f"\n{'=' * 70}")
    print("  Demo complete.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
