# Secure Distributed Cloud Storage

Educational / prototype project: a distributed-style cloud storage backend
with JWT authentication, PostgreSQL, simulated multi-node distributed
storage, OpenCV-based face authentication, and an admin/monitoring
dashboard.

> ⚠️ **This is a learning project, not a production system.** In
> particular, the OpenCV face authentication feature (added in a later
> phase) is a basic prototype for demonstration purposes. It is **not**
> a production-grade biometric security system and should not be relied
> on to protect real sensitive data.

## Status

All 9 phases are implemented — see the phase-by-phase sections below
for what was built and how to test each one. For running this in the
cloud instead of locally, see **[DEPLOYMENT.md](DEPLOYMENT.md)**
(Render + Neon + Cloudflare R2 — genuinely free, forever) or
**[QUICKSTART_DEPLOY.md](QUICKSTART_DEPLOY.md)** for the condensed
checklist version. For self-hosting on your own hardware instead, see
**[DEPLOY_RASPBERRY_PI.md](DEPLOY_RASPBERRY_PI.md)** or
**[QUICKSTART_RASPBERRY_PI.md](QUICKSTART_RASPBERRY_PI.md)** for its
condensed checklist.

- [x] Phase 0 — Project setup, FastAPI bootstrap, PostgreSQL connection check
- [x] Phase 1 — Database schema (users, files, storage_nodes, login_logs, audit_logs, face_auth_logs)
- [x] Phase 2 — Authentication (register / login / JWT / `/auth/me`)
- [x] Phase 3 — Dashboard (aggregate stats)
- [x] Phase 4 — File upload/download
- [x] Phase 5 — Distributed storage (round-robin across node1/node2/node3)
- [x] Phase 6 — OpenCV face authentication (prototype)
- [x] Phase 7 — Admin APIs
- [x] Phase 8 — Monitoring, audit log, notification
- [x] Phase 9 — Testing

Later phases are built incrementally, on request, one at a time.

## Tech stack

- Python 3.10, FastAPI, Uvicorn
- PostgreSQL 18 (psycopg2-binary) — **PostgreSQL only, no SQLite**
- bcrypt (password hashing), python-jose (JWT)
- OpenCV (face authentication, Phase 6)
- python-dotenv, Pydantic, python-multipart

## Project structure

```
secure-distributed-cloud-storage/
├── backend/
│   ├── core/        # config.py, security.py
│   ├── database/     # database.py, models.py
│   ├── routers/       # auth, users, files, face, dashboard, admin, monitor
│   ├── services/      # auth, file, face, node, notification services
│   ├── utils/          # jwt helpers, logger
│   └── main.py
├── storage/
│   ├── node1/  node2/  node3/   # simulated distributed storage nodes
├── tests/
├── .env / .env.example
├── requirements.txt
└── README.md
```

## Setup (Windows PowerShell)

### 1. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file and edit it with your real PostgreSQL password and a
random secret key:

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` must define:

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/cloud_storage
SECRET_KEY=CHANGE_ME
```

Never commit `.env` — it's already in `.gitignore`.

### 4. Create the PostgreSQL database

If `psql` is not on your PATH, use the full path to PostgreSQL 18's binary:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE cloud_storage;"
```

Or, if `psql` is already on PATH:

```powershell
psql -U postgres -c "CREATE DATABASE cloud_storage;"
```

### 5. Run the API

```powershell
uvicorn backend.main:app --reload
```

### 6. Test

Open in your browser:

- http://127.0.0.1:8000 — health check (should show `"database": "connected"`)
- http://127.0.0.1:8000/docs — interactive Swagger UI

Check the terminal running `uvicorn` for startup logs. You should see:

```
[startup] PostgreSQL connection: OK
[startup] Schema init: OK (users, files, storage_nodes, login_logs, audit_logs, face_auth_logs; node1/node2/node3 seeded)
```

If `"database": "disconnected"` appears, check:

1. PostgreSQL 18 service is running
2. `cloud_storage` database exists
3. `DATABASE_URL` in `.env` has the correct password
4. Port 5432 is not blocked by a firewall

### 7. Verify the schema directly (optional but recommended)

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "\dt"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "SELECT * FROM storage_nodes;"
```

`\dt` should list all 6 tables. The `storage_nodes` query should show 3
rows (`node1`, `node2`, `node3`), all `status = online`.

## Next step

Once Phase 1 is confirmed working (all 6 tables exist, storage_nodes has
3 seeded rows), continue to Phase 2 (below).

## Phase 2 — Authentication

Endpoints added:

- `POST /auth/register` — JSON body `{"username", "email", "password"}` → creates a user (password hashed with bcrypt, never stored in plaintext). Returns `409` if username/email already taken.
- `POST /auth/login` — **form data** (not JSON): `username` + `password`. Returns `{"access_token": "...", "token_type": "bearer"}`. Also writes a row to `login_logs` (success or failed, with IP).
- `GET /auth/me` — requires `Authorization: Bearer <token>`. Returns the current user's profile.

Login uses `OAuth2PasswordRequestForm` (standard FastAPI form-based
login) instead of JSON. This is intentional: it lets Swagger UI's
**Authorize** button (top right of `/docs`) get and attach a Bearer
token automatically, so you can test protected endpoints directly
from the browser.

JWT payload contains `user_id`, `username`, `role`, `exp` and is
signed with `SECRET_KEY`/`ALGORITHM` from `.env`.

### Test via Swagger UI (recommended)

1. Go to `http://127.0.0.1:8000/docs`
2. Expand `POST /auth/register`, "Try it out", use e.g.:
   ```json
   { "username": "test", "email": "test@example.com", "password": "123456" }
   ```
   → should return `201` with the new user's public fields (no password_hash).
3. Try registering the same username again → should return `409`.
4. Click **Authorize** (top right, padlock icon) → enter `username: test`, `password: 123456` → Authorize.
5. Expand `GET /auth/me`, "Try it out", Execute → should return the same user's profile (now authenticated via the token Swagger attached automatically).
6. Expand `POST /auth/login` directly, "Try it out", fill in the form fields → should return an `access_token`.

### Test via PowerShell (curl)

```powershell
# Register
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/register `
  -ContentType "application/json" `
  -Body '{"username":"test","email":"test@example.com","password":"123456"}'

# Login (form-encoded)
$resp = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/auth/login `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "username=test&password=123456"
$token = $resp.access_token

# Me
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/auth/me `
  -Headers @{ Authorization = "Bearer $token" }
```

### Verify login_logs in psql

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "SELECT * FROM login_logs ORDER BY id DESC LIMIT 5;"
```

Should show a `success` row for the login above. Try logging in with
the wrong password once — a `failed` row should appear too.

## Next step

Once Phase 2 is confirmed working, continue to Phase 3 (below).

## Phase 3 — Dashboard

- `GET /dashboard` — requires `Authorization: Bearer <token>` (any
  logged-in user; not public, since it exposes user/file counts).

Response:

```json
{
  "users": 1,
  "files": 0,
  "storage_used": 0,
  "nodes": 3,
  "online_nodes": 3,
  "login_count": 1,
  "node_status": [
    { "node_name": "node1", "status": "online", "total_files": 0, "total_size": 0 },
    { "node_name": "node2", "status": "online", "total_files": 0, "total_size": 0 },
    { "node_name": "node3", "status": "online", "total_files": 0, "total_size": 0 }
  ]
}
```

`files`, `storage_used`, and each node's `total_files`/`total_size`
will read `0` until Phase 4 (file upload) exists — that's expected
right now.

### Test via Swagger UI

1. `http://127.0.0.1:8000/docs`
2. If not already authorized from Phase 2, click **Authorize** and log in with a registered user.
3. Expand `GET /dashboard`, "Try it out", Execute.
4. Should return `200` with `nodes: 3`, `online_nodes: 3` (seeded in Phase 1), and `users` matching how many accounts you've registered.
5. Log out (click Authorize → Logout) and try `GET /dashboard` again without a token → should return `401`.

### Test via PowerShell

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/dashboard `
  -Headers @{ Authorization = "Bearer $token" }
```

(`$token` from the Phase 2 login example.)

## Next step

Once Phase 3 is confirmed working, continue to Phase 4 (below).

## Phase 4 — File Upload

Endpoints added (all require `Authorization: Bearer <token>`):

- `POST /files/upload` — multipart form, field name `file`. Returns file metadata (`201`).
- `GET /files` — list only the current user's own files.
- `GET /files/{id}` — metadata for one file. `404` if it doesn't exist, `403` if it belongs to another user.
- `GET /files/{id}/download` — streams the file back with its original filename.
- `DELETE /files/{id}` — deletes the DB row and the file on disk (`204`).

Security measures implemented:

- **Ownership** — every per-file route checks `file.user_id == current_user.user_id`; otherwise `403`.
- **Path traversal** — the filename you upload is sanitized for
  *display* only (`original_filename` in the DB); the actual on-disk
  filename is always a fresh server-generated UUID, so user input
  never touches the filesystem path. Downloads/deletes also verify
  the resolved path stays inside `storage/`.
- **Oversized upload** — capped at `MAX_UPLOAD_SIZE_MB` (default 20 MB,
  configurable in `.env`); exceeding it aborts mid-stream with `413`
  rather than buffering the whole file first.
- **Empty upload** — rejected with `400`.
- **Checksum** — SHA-256 computed over the uploaded bytes and stored in `files.checksum`.

Design notes:

- `storage_node` is fixed to `"node1"` for every upload right now.
  Phase 5 adds real round-robin selection across `node1`/`node2`/`node3`
  via `node_service.py` — the DB schema and this API already support
  any node name, so that phase won't require changing this one.
- `storage_nodes.total_files` / `total_size` are updated on every
  upload/delete, so the Phase 3 dashboard numbers stay accurate.
- MIME type is taken from the client's `Content-Type` header (no
  magic-byte sniffing library is in the approved tech stack) — good
  enough for a prototype, but worth knowing if you extend this later.

### Test via Swagger UI

1. `/docs` → Authorize with a logged-in user (from Phase 2).
2. `POST /files/upload` → "Try it out" → choose a small test file → Execute. Should return `201` with `checksum`, `file_size`, `storage_node: "node1"`.
3. `GET /files` → should list the file you just uploaded.
4. `GET /files/{id}/download` → should return the raw file content.
5. `DELETE /files/{id}` → `204`. `GET /files/{id}` afterward → `404`.

### Test ownership protection

1. Register a second user (`POST /auth/register` with a different username/email).
2. Authorize as that second user.
3. Try `GET /files/{id}` using the *first* user's file id → should return `403`.

### Verify on disk / in DB

```powershell
dir storage\node1
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "SELECT id, original_filename, storage_node, file_size, checksum FROM files;"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "SELECT node_name, total_files, total_size FROM storage_nodes;"
```

## Next step

Once Phase 4 is confirmed working, continue to Phase 5 (below).

## Phase 5 — Distributed Storage

No new routes. `POST /files/upload` now calls
`node_service.select_node()` instead of always using `node1`.

**`backend/services/node_service.py`** (new):

- `select_node()` — round-robin over currently `online` nodes, keyed
  off the total number of files uploaded so far
  (`total_files % number_of_online_nodes`). With all 3 nodes online:
  `node1 → node2 → node3 → node1 → ...`, matching the spec's example.
  Raises `503` if every node is offline.
- `get_all_nodes()` / `get_online_node_names()` — read helpers, reused
  by the admin/monitoring routers in later phases.
- `set_node_status()` — flips a node online/offline. Not wired to an
  API route yet (that's Phase 7's `/admin/nodes`) - for now, test
  failover by updating `storage_nodes.status` directly in psql.

**`backend/routers/files.py`** — upload now calls
`node_service.select_node()` and stores whichever node it returns,
instead of a hardcoded `"node1"`.

Known limitation (fine for a prototype): the round-robin key is
`COUNT(*) FROM files`, so deleting files can shift the rotation
slightly out of a perfect 1-2-3-1-2-3 pattern. Good enough to
demonstrate the concept — a real implementation would track an
explicit rotation cursor.

### Test round-robin distribution

1. Make sure all 3 nodes are online:
   ```powershell
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "SELECT node_name, status FROM storage_nodes;"
   ```
2. Via Swagger UI (`/docs`, Authorize first), upload 4-5 small files in a row using `POST /files/upload`.
3. Check where they landed:
   ```powershell
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "SELECT id, original_filename, storage_node FROM files ORDER BY id;"
   ```
   You should see `storage_node` cycling `node1, node2, node3, node1, node2, ...`.
4. Confirm the files actually landed in the matching folders:
   ```powershell
   dir storage\node1
   dir storage\node2
   dir storage\node3
   ```

### Test node failover (offline node is skipped)

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "UPDATE storage_nodes SET status = 'offline' WHERE node_name = 'node2';"
```

Upload a couple more files via Swagger — none of them should land on
`node2` while it's offline. Set it back online when done:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "UPDATE storage_nodes SET status = 'online' WHERE node_name = 'node2';"
```

### Test total outage

Set all 3 nodes offline, then try `POST /files/upload` → should return
`503 Service Unavailable`. Set them back online afterward.

## Next step

Once Phase 5 is confirmed working, continue to Phase 6 (below).

## Phase 6 — OpenCV Face Authentication

> ⚠️ **Prototype only.** This is Haar-cascade face detection plus a
> simple appearance-based descriptor (downsize → blur → equalize →
> mean-center → cosine similarity) - not a trained deep-learning face
> embedding, and it has **no liveness detection** (a printed photo or
> a video of someone's face on a phone screen can pass verification).
> Do not use this to protect anything actually sensitive. See the
> docstring in `backend/services/face_service.py` for the full
> reasoning.

Endpoints added (both require `Authorization: Bearer <token>`,
multipart form field name `file`, image only):

- `POST /face/register` — detects a face in the uploaded photo, saves an "encoding" (`storage/faces/user_<id>.npy`), and records the path in `users.face_encoding_path`.
- `POST /face/verify` — detects a face in the uploaded photo, compares it to your registered encoding, returns `{"verified": bool, "confidence": float}`, and logs the attempt to `face_auth_logs`.

Errors:
- `400` — no face detected, image unreadable, or empty upload.
- `404` (verify only) — you haven't called `/face/register` yet.
- `413` — image over 8 MB.

**The "camera" step is client-side.** This backend never touches a
webcam directly - `POST /face/register`/`/verify` just receive an
already-captured JPEG/PNG file, the same way a phone app or browser
`<input type="file" capture>` would send one.

**Tuning the threshold:** `FACE_VERIFY_THRESHOLD` in `.env` (default
`0.90`) is an untested starting point, not a calibrated value. If
verifying with your own face fails, lower it slightly; if a different
photo wrongly "verifies," raise it. Test with your own webcam photos,
not the synthetic images used during development.

### Test via Swagger UI

1. `/docs` → Authorize with a logged-in user.
2. `POST /face/register` → upload a clear, front-facing, well-lit photo of a face (a phone selfie works). Should return `201`-style success with `face_encoding_path`.
3. `POST /face/verify` → upload another photo of the **same** face → expect `verified: true` with a high `confidence`.
4. Try `/face/verify` again with a photo of a **different** face (or a photo with no face, like a landscape) → expect `verified: false` (or `400` if no face is detected at all).

### Verify in psql

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "SELECT id, face_encoding_path FROM users;"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "SELECT * FROM face_auth_logs ORDER BY id DESC LIMIT 5;"
dir storage\faces
```

## Next step

Once Phase 6 is confirmed working, continue to Phase 7 (below).

## Phase 7 — Admin APIs

New dependency: **`get_current_admin_user`** (in `core/security.py`) —
built on `get_current_user`, additionally requires `role == "admin"`
in the JWT, else `403`. Applied to the whole `/admin` router at once.

Endpoints added (all require `Authorization: Bearer <token>` from an
**admin** account, all support an optional `?limit=` query param,
default 100, max 500):

- `GET /admin/users` — every user's public fields.
- `GET /admin/files` — every file, with the owning username joined in.
- `GET /admin/logins` — every login attempt (success and failed), newest first.
- `GET /admin/audit-logs` — every audit log entry. **Empty for now** — Phase 8 wires up the actual `INSERT`s; this endpoint/table already exist so Phase 8 won't need any new routes.
- `GET /admin/nodes` — the 3 storage nodes with status/usage stats (reuses `node_service.get_all_nodes()` from Phase 5).

**Note:** role comes from the JWT claims, not re-checked against the
DB per-request — if you demote an admin, their existing token stays
valid (as admin) until it expires. Fine for a short-lived-token
prototype.

### Getting an admin account to test with

`POST /auth/register` always creates `role = 'user'` (registering
yourself as admin would be a privilege-escalation bug) — promote a
user to admin directly in the DB:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "UPDATE users SET role = 'admin' WHERE username = 'test';"
```

Then **log in again** (`/auth/login`) so the new JWT carries
`role: admin` — the old token still says `role: user` until it
expires.

### Test via Swagger UI

1. Promote a user to admin (above), then Authorize with that user's fresh token.
2. `GET /admin/users` → should list every registered user, not just yourself.
3. `GET /admin/files` → should show files from every user (try uploading as two different users first, if you haven't already).
4. `GET /admin/nodes` → should match what `/dashboard` and `/monitor/nodes` (Phase 8) report.
5. `GET /admin/audit-logs` → returns `[]` right now — expected until Phase 8.

### Test that regular users are blocked

1. Authorize with a non-admin user.
2. `GET /admin/users` → should return `403 Forbidden`.

## Next step

Once Phase 7 is confirmed working, continue to Phase 8 (below).

## Phase 8 — Monitoring, Audit Log, Notification

### Monitoring (`backend/routers/monitor.py`)

Public, no JWT required (health checks conventionally can't
authenticate — load balancers, uptime monitors, container
orchestrators):

- `GET /monitor/health` — matches the spec's example shape exactly:
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "nodes": { "node1": "online", "node2": "online", "node3": "online" }
  }
  ```
- `GET /monitor/nodes` — more detail per node (`status`, `total_files`, `total_size`), still public.

### Notification (`backend/services/notification_service.py`)

Single entry point `notify(user_id, username, action, target, details)`
used everywhere else in the app. Per spec, no SMS yet — writes to two
channels:
- **console** — printed as e.g. `[notification] User admin uploaded file test.pdf`
- **database** — a row in `audit_logs` (the schema has no separate
  `notifications` table; `audit_logs` already has the right shape, so
  it doubles as the durable notification record)

Adding Email/Discord/LINE later means adding one function + one call
inside `notify()`, not touching every call site.

### Audit Log

`notify()` is now called at every event from the spec's list:

| Action | Where |
|---|---|
| `REGISTER` | `POST /auth/register` |
| `LOGIN` | `POST /auth/login` (success only — failed attempts are already tracked separately in `login_logs` since Phase 2) |
| `UPLOAD` | `POST /files/upload` |
| `DOWNLOAD` | `GET /files/{id}/download` |
| `DELETE` | `DELETE /files/{id}` |
| `FACE_REGISTER` | `POST /face/register` |
| `FACE_VERIFY` | `POST /face/verify` |
| `ADMIN_ACTION` | every `/admin/*` listing endpoint |

**`LOGOUT` is not implemented.** JWTs here are stateless (no server-
side session), so there's nothing to invalidate server-side — logging
out is just the client discarding its token. This is a deliberate
simplification, not an oversight; a production system wanting real
logout would need a token blocklist/short-lived-refresh-token scheme.

`GET /admin/audit-logs` (Phase 7) now returns real rows.

### Test via Swagger UI

1. `GET /monitor/health` — no Authorize needed. Should return the exact shape above.
2. `GET /monitor/nodes` — no Authorize needed.
3. Do a few actions while logged in as a regular user: register (if you haven't already), login, upload a file, download it, delete it, register/verify a face.
4. Authorize as an admin, `GET /admin/audit-logs` → should now show rows for every action above, newest first, with human-readable-ish `action`/`target`/`details`.
5. Check your terminal running `uvicorn` — you should see `[notification] User ... ...` lines printed as you did each action in step 3.

### Verify in psql

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cloud_storage -c "SELECT id, user_id, action, target, timestamp FROM audit_logs ORDER BY id DESC LIMIT 15;"
```

## Next step

Once Phase 8 is confirmed working, continue to Phase 9 (below) — the
final phase.

## Phase 9 — Testing

Test dependencies (`pytest`, `httpx`) are **not** in `requirements.txt`
— section 1's tech-stack list is for the backend runtime, and these
are tools used to verify the backend, not part of it. They live in a
separate `requirements-dev.txt`.

```
tests/
├── conftest.py           # shared fixtures: TestClient, register_user(), register_admin(), etc.
├── test_auth.py           # Phase 2 — register/login/me, duplicates, bad password, bad token
├── test_jwt.py             # Phase 2 — token create/decode, malformed & expired tokens (no DB needed)
├── test_files.py            # Phase 4 — upload/list/get/download/delete, ownership, 404/400
├── test_authorization.py     # Phase 2/7 — 401 without token, 403 for non-admin on /admin/*
├── test_storage_nodes.py      # Phase 5 — round-robin across nodes, offline-node skip, total outage → 503
├── test_dashboard.py           # Phase 3 — auth required, response shape
└── test_admin.py                 # Phase 7 — admin sees all users/files/nodes/audit-logs/logins
```

### 1. Install test dependencies

```powershell
pip install -r requirements-dev.txt
```

### 2. (Recommended) create a separate test database

Tests register real users and upload real files against whatever
`DATABASE_URL` is active — running them against your everyday dev
database will leave it full of `testuser_xxxxx` accounts. A separate
test DB avoids that:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE cloud_storage_test;"
```

Then set (in your PowerShell session, or add it to `.env` — either
works since `conftest.py` reads `TEST_DATABASE_URL` at import time and
overrides `DATABASE_URL` for the test run only if it's set):

```powershell
$env:TEST_DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/cloud_storage_test"
```

If you skip this step, tests run against your regular `DATABASE_URL`
from `.env` — that's fine too, just noisier.

### 3. Run the tests

```powershell
pytest -v
```

`conftest.py` creates the schema in the target DB automatically
(reuses Phase 1's `init_schema()`) before any test runs, so a brand
new empty test database works out of the box — no manual `CREATE
TABLE` needed.

### Notes on how these tests work

- Every test that needs a user calls the `register_user()` fixture,
  which registers with a fresh random username (`testuser_<8 hex
  chars>`) each time — tests never collide with each other or with
  data from a previous run, and can be re-run repeatedly without
  cleanup.
- `register_admin()` registers a normal user, then promotes them to
  `role='admin'` directly via SQL (mirroring the manual-promotion
  process from Phase 7) and re-logs-in for a fresh admin-role token.
- File tests clean up what they create (`finally: client.delete(...)`)
  so repeated runs don't pile up storage on disk.
- `test_storage_nodes.py` directly flips `storage_nodes.status` in the
  DB to test the offline-skip and total-outage (`503`) paths, then
  restores all 3 nodes to `online` afterward (in a `finally` block, so
  a failed assertion still restores node state for the next test run).
- `test_jwt.py` needs no DB at all — it calls `utils/jwt.py` directly.

### Expected result

All tests should pass against a correctly configured PostgreSQL
instance. If something fails:

- Connection errors → check `DATABASE_URL`/`TEST_DATABASE_URL` and that PostgreSQL is running.
- `test_face_*` isn't included here — Phase 6's face endpoints need real photo uploads, which don't lend themselves to fully automated testing; verify those manually via Swagger as described in the Phase 6 section above.

---

## That's all 9 phases.

The project now implements every section of the original spec:
authentication (bcrypt + JWT), PostgreSQL storage, file upload/
download with ownership checks, simulated distributed storage with
round-robin + failover, an OpenCV face-authentication prototype,
admin APIs, monitoring, audit logging via a unified notification
service, and an automated test suite. See each phase's section above
for what was built and how to verify it.

## Want to see it all run at once? `demo.py`

A single script that exercises the whole API end-to-end against your
real running server + real PostgreSQL - registers a user, logs in,
hits the dashboard, uploads/downloads/deletes a file, registers and
verifies a face (using an auto-generated synthetic photo, so you
don't need a webcam), promotes itself to admin, and hits every admin
+ monitoring endpoint. Prints each request/response as it goes.

Uses only stdlib (`urllib`) for HTTP plus `psycopg2`/`python-dotenv`
(already required by the app) - no extra installs needed.

```powershell
# Terminal 1
uvicorn backend.main:app --reload

# Terminal 2
python demo.py
```

Expect ~25 request/response blocks printed, ending with `Demo
complete.`. If the admin-promotion step can't reach the DB directly
(e.g. different `DATABASE_URL` context), it prints a note and the
admin endpoints show `403` instead of `200` - the rest of the demo
still runs.

**Known gaps, honestly noted:** `backend/routers/users.py` and
`backend/utils/logger.py` are still empty placeholders from the
Phase 0 skeleton. None of the 9 phases ended up requiring them —
user profile access is covered by `GET /auth/me` and
`GET /admin/users`, and all logging in this project goes through
`notification_service.py`'s console output rather than a separate
logger module. Left as-is rather than adding unrequested endpoints/
utilities just to fill the files.

## Web UI — `frontend/index.html`

A dashboard-style web UI (per section 1: "Frontend ในระยะแรกให้ทำเป็น
Web UI ธรรมดา"), styled as a **Modern Enterprise Cloud Storage / Cyber
Security Ops Console**: dark charcoal base, electric blue + cyan
accent, subtle glassmorphism on cards, collapsible sidebar with
section grouping (Platform / Management). One self-contained HTML
file, no build step, no npm install. Same API contract throughout —
every enhancement pass has been visual/UX only; no endpoint, request
shape, or backend behavior has ever changed.

**CORS is enabled wide-open** (`allow_origins=["*"]`) in
`backend/main.py` specifically so this file can call the API from a
browser — noted there as a dev-only setting, not something to carry
into a real deployment.

### Run it

```powershell
# Terminal 1
uvicorn backend.main:app --reload
```

Then just open `frontend/index.html` directly in a browser (double-
click it, or right-click → Open with → your browser). No server
needed for the frontend itself — it's a static file that talks to
your API at `http://127.0.0.1:8000` (editable in **Settings**).

### What's on each page

- **Overview** — stat cards, a "storage by node" bar chart, a "your
  file types" donut chart (computed client-side from your actual
  files' extensions), recent files, and node status. Admins get two
  extra panels: login activity by day and a security activity
  timeline — both real data from `/admin/logins` and
  `/admin/audit-logs`.
- **My Files** — drag-and-drop upload with a real progress bar (via
  `XMLHttpRequest`, tracking actual bytes sent — not a fake timer),
  type filter, sort, list/grid view toggle, and a confirmation dialog
  before delete.
- **Storage (Node Manager)** — live per-node cards + comparison bars. Public endpoint, works even logged out.
- **Security Center** — subsystem status (auth/JWT/DB/file-integrity/face-auth), and for admins: successful/failed login counts, face-verification count, and a security activity timeline. All computed from existing endpoints — no new backend routes.
- **Face Authentication** — register/verify with real photos; same prototype warning as the API.
- **System Logs** — public health status for everyone; login & audit tables for admins only.
- **Admin Panel** — the 5 listing endpoints, admin-only, search bar filters whichever table is loaded.
- **Settings** — API base URL, theme toggle, session info, logout, and a short "about this build" note.

### Design notes

- **All data is real — nothing is fabricated.** There's no "storage
  over the last 7 days" trend line, because this backend doesn't store
  historical snapshots (only current totals) — a fake trend would be
  misleading, so it's a live per-node bar chart instead. The
  notification bell and Security Center's counters/timeline only
  populate for admins, because that's the only role with endpoints
  that return them (`/admin/logins`, `/admin/audit-logs`) — a regular
  user has no personal activity-log endpoint to draw from.
- Charts (bar + donut) are hand-drawn SVG, not a charting library — no
  CDN dependency to go stale or fail to load.
- Light/dark theme toggle and the sidebar collapse state are
  in-memory only (consistent with the session token) — nothing is
  written to browser storage anywhere in this file.
- Every state a real product needs is covered: loading (skeleton
  rows), empty (icon + message + next action), and error (retry
  button) — not just the happy path.

I verified this file with a headless browser against a mock server
during development — logged in, walked every page including the new
Security Center, opened the delete-confirmation modal, toggled
light/dark theme, collapsed the sidebar, opened the notification
dropdown, and checked a mobile viewport — before shipping it, not
after.
