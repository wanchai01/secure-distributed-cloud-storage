"""
Notification service (Phase 8).

Per spec: no SMS in this phase. Supports:
- console notification: printed to stdout
- database notification: a row in `audit_logs`

The project's DB design (Phase 1) has no separate `notifications`
table - `audit_logs` (user_id, action, target, details, timestamp)
already models "user did X to Y, here's why", so it doubles as the
durable notification record here rather than duplicating a second
table with the same shape.

`notify()` is the single entry point every other part of the app
calls. Adding Email/Discord/LINE later means adding one more function
+ one more call inside `notify()`, not touching every call site.
"""

from typing import Optional

from backend.database.database import get_connection

# The action vocabulary from the spec (section 14). Not strictly
# enforced - an unrecognized action still gets logged, just with a
# generic console phrasing.
ACTION_VERBS = {
    "REGISTER": "registered",
    "LOGIN": "logged in",
    "LOGOUT": "logged out",
    "UPLOAD": "uploaded file",
    "DOWNLOAD": "downloaded file",
    "DELETE": "deleted file",
    "FACE_REGISTER": "registered a face",
    "FACE_VERIFY": "attempted face verification",
    "ADMIN_ACTION": "performed an admin action",
}


def _console_notify(message: str) -> None:
    print(f"[notification] {message}")


def _db_notify(
    user_id: Optional[int],
    action: str,
    target: Optional[str],
    details: Optional[str],
) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (user_id, action, target, details)
                VALUES (%s, %s, %s, %s);
                """,
                (user_id, action, target, details),
            )
        conn.commit()
    finally:
        conn.close()


def notify(
    user_id: Optional[int],
    username: Optional[str],
    action: str,
    target: Optional[str] = None,
    details: Optional[str] = None,
) -> None:
    """
    Record one event to both channels: console + audit_logs.

    Example: notify(1, "admin", "UPLOAD", target="test.pdf")
    -> console: "[notification] User admin uploaded file test.pdf"
    -> audit_logs row: (user_id=1, action="UPLOAD", target="test.pdf", ...)
    """
    who = username or (f"user#{user_id}" if user_id else "unknown user")
    verb = ACTION_VERBS.get(action, action.lower())
    message = f"User {who} {verb}"
    if target:
        message += f" {target}"

    _console_notify(message)
    _db_notify(user_id, action, target, details)
