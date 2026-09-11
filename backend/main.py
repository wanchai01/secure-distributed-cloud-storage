"""
Secure Distributed Cloud Storage - FastAPI entrypoint.

Phase 0: App bootstrap, "/" health endpoint, PostgreSQL connectivity
check on startup (does not crash the app, just logs status - so /docs
still loads even if DB is down).

Phase 1: On successful DB connection, startup also creates all tables
(users, files, storage_nodes, login_logs, audit_logs, face_auth_logs)
and seeds the 3 simulated storage nodes. Idempotent - safe on every
restart.

Phase 2: Authentication routes (register/login/me) are mounted via
backend.routers.auth.

Phase 3: Dashboard route (aggregate stats) mounted via
backend.routers.dashboard.

Phase 4: File routes (upload/list/get/download/delete) mounted via
backend.routers.files.

Phase 5: File uploads now pick a storage node via node_service's
round-robin selection (no new routes - files.py was updated in place).

Phase 6: Face authentication routes (register/verify) mounted via
backend.routers.face. Prototype only - see face_service.py docstring.

Phase 7: Admin routes (users/files/logins/audit-logs/nodes listings,
role='admin' only) mounted via backend.routers.admin.

Phase 8: Monitoring routes (public health/status) mounted via
backend.routers.monitor. Every write-side route across the app now
also calls notification_service.notify() (console print + a row in
audit_logs), so /admin/audit-logs starts filling in from this phase
onward.

Frontend: CORS is enabled wide-open (allow_origins=["*"]) so the
simple web UI in frontend/index.html (a static HTML file opened
straight from disk, or served separately) can call this API from the
browser. Fine for this local prototype; a real deployment would
restrict this to the frontend's actual origin.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.database.database import init_schema, test_connection
from backend.routers import admin as admin_router
from backend.routers import auth as auth_router
from backend.routers import dashboard as dashboard_router
from backend.routers import face as face_router
from backend.routers import files as files_router
from backend.routers import monitor as monitor_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Educational prototype: distributed cloud storage with "
    "JWT auth, PostgreSQL, and OpenCV-based face authentication. "
    "Not intended for production security use.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(files_router.router)
app.include_router(face_router.router)
app.include_router(admin_router.router)
app.include_router(monitor_router.router)


@app.on_event("startup")
def on_startup() -> None:
    """Validate config and report DB connectivity at boot."""
    settings.validate()
    if test_connection():
        print("[startup] PostgreSQL connection: OK")
        if init_schema():
            print(
                "[startup] Schema init: OK "
                "(users, files, storage_nodes, login_logs, audit_logs, "
                "face_auth_logs; node1/node2/node3 seeded)"
            )
        else:
            print("[startup] Schema init: FAILED (see error above)")
    else:
        print(
            "[startup] PostgreSQL connection: FAILED "
            "(check .env DATABASE_URL and that PostgreSQL is running)"
        )


@app.get("/")
def health_check():
    """Basic liveness check for Phase 0."""
    db_ok = test_connection()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": "connected" if db_ok else "disconnected",
    }
