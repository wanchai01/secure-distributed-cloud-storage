# Deployment Guide

This backend (FastAPI + PostgreSQL + OpenCV) can't run on Cloudflare
Workers (no native filesystem, no long-running process, no native
C-extension support for OpenCV/psycopg2). This guide covers real
container hosts that support the stack directly.

> **A correction, for the record:** an earlier version of this guide
> said you could attach a free persistent disk on Render to keep
> uploaded files. That was wrong. **Render's free web service tier
> cannot attach a persistent disk at all** — any file written to local
> disk is wiped on every redeploy, restart, *or spin-down* (which
> happens after just 15 minutes of inactivity). A disk requires a paid
> plan ($7/mo+). This guide now uses Cloudflare R2 instead, which
> fixes that for real, at $0.

## The recommended setup: genuinely free, forever

| Piece | Where | Why |
|---|---|---|
| App (this backend) | **Render** free web service | Free web hosting, Docker support, no card required |
| Database | **Neon** free Postgres | Permanent free tier (no 30-day expiry like Render's own Postgres) |
| File / face storage | **Cloudflare R2** | 10 GB genuinely free forever; fixes Render's lack of a free persistent disk |

None of these require a credit card at the free tier used here. The
tradeoff you're accepting: Render's free web service spins down after
15 minutes idle (about 1 minute cold start on the next request), and
Neon's compute also scales to zero when idle (300-800ms cold start).
Fine for a prototype/personal project; annoying if you want zero
latency 100% of the time - that requires paid tiers on one or both.

Three files in this repo support this setup already:
- **`Dockerfile`** - builds the backend, including the system libraries `opencv-python-headless` needs.
- **`.dockerignore`** - keeps `.env` and dev-only files out of the image.
- **`render.yaml`** - a Render Blueprint that creates the web service and prompts you for the Neon/R2 values during setup.

And code changes already made for this:
- `requirements.txt` uses **`opencv-python-headless`** (no GUI bindings this project doesn't use) and adds **`boto3`** (for talking to R2's S3-compatible API).
- `backend/services/storage_backend.py` is a small abstraction: `STORAGE_BACKEND=local` (default) behaves exactly like Phases 0-9; `STORAGE_BACKEND=r2` sends the same reads/writes to R2 instead. Nothing else in the codebase changed - `file_service.py` and `face_service.py` just call `storage_backend.upload/download/delete` instead of touching `Path` objects directly.

---

## 1. Set up Neon (database)

1. Go to [neon.tech](https://neon.tech) and sign up (no card required).
2. **Create a project**. Pick a region close to where you'll deploy (Render's free tier defaults to Oregon, US).
3. On the project dashboard, click **Connect**. You'll see two connection strings:
   - **Pooled** (hostname contains `-pooler`) - use this one. This app opens a fresh `psycopg2` connection per request rather than keeping a long-lived pool, so the pooled endpoint avoids exhausting Postgres' connection limit under load.
   - Direct - not needed here.
4. Copy the pooled connection string. It looks like:
   ```
   postgresql://user:password@ep-xxx-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
   ```
   Save it - you'll paste it into Render as `DATABASE_URL` in step 4. No code changes needed: `psycopg2.connect()` accepts this URL format directly, `sslmode=require` included.

> Free tier: 0.5 GB storage, compute scales to zero after ~5 min idle. Plenty for this project's tables.

---

## 2. Set up Cloudflare R2 (file storage)

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) and sign up if needed (no card required for R2's free tier).
2. In the sidebar: **R2 Object Storage** -> **Create bucket**. Name it e.g. `cloud-storage-uploads`. Location: Automatic.
3. Get your **Account ID**: shown on the R2 overview page (right sidebar), or in your dashboard's URL.
4. Create API credentials: **R2** -> **Manage API Tokens** -> **Create API Token**.
   - Permissions: **Object Read & Write**
   - Scope it to the bucket you just created (not all buckets, for least privilege)
   - Click **Create API Token** -> copy the **Access Key ID** and **Secret Access Key** shown (the secret is shown once - save it now)

You now have 4 values: Account ID, Access Key ID, Secret Access Key, Bucket Name. You'll paste these into Render in step 4.

> Free tier: 10 GB storage, 1 million Class A (write) + 10 million Class B (read) operations/month, **zero egress fees** (R2's headline feature vs S3). Generous for a prototype.

---

## 3. Push this repo to GitHub

```powershell
cd secure-distributed-cloud-storage
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

(`.env` is in `.gitignore` - your real secrets never get pushed. `git add .` is correct and safe here; `.gitignore` filters out what shouldn't go up.)

---

## 4. Deploy to Render

1. Go to [render.com](https://render.com) and sign in with GitHub.
2. **New** -> **Blueprint** -> select your repo. Render reads `render.yaml`.
3. Render shows a preview of one web service, with several environment
   variables marked for manual entry. Fill them in:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon pooled connection string from step 1 |
   | `R2_ACCOUNT_ID` | from step 2 |
   | `R2_ACCESS_KEY_ID` | from step 2 |
   | `R2_SECRET_ACCESS_KEY` | from step 2 |
   | `R2_BUCKET_NAME` | from step 2 (e.g. `cloud-storage-uploads`) |

   (`SECRET_KEY` is auto-generated by the blueprint; `STORAGE_BACKEND=r2` and the rest are already set.)
4. Click **Apply**. Render builds the Docker image and deploys.
5. Once live, you'll get a URL like `secure-distributed-cloud-storage.onrender.com`.

### Verify

```powershell
curl https://your-app.onrender.com/monitor/health
```

Should return `{"status":"healthy","database":"connected",...}`. If
`database` says `disconnected`, double check the Neon connection
string (common mistake: copying the *direct* string instead of the
*pooled* one, or missing `?sslmode=require`).

Test the storage backend actually reaches R2: register a user, log
in, upload a small file via `/docs` on your deployed URL, then check
the Cloudflare dashboard - **R2** -> your bucket -> you should see an
object under `node1/` (or node2/node3). If it's there, R2 is wired up
correctly.

---

## 5. After deploying

- **Promote an admin**: same as local dev - register a user through
  the API, then run this against your Neon database (Neon's dashboard
  has a **SQL Editor** you can paste this into directly, no `psql`
  install needed):
  ```sql
  UPDATE users SET role = 'admin' WHERE username = 'yourusername';
  ```
  Then log in again so the new JWT carries `role: admin`.
- **Schema creation is automatic** - `init_schema()` (Phase 1) runs on
  every startup, so the first deploy creates all 6 tables and seeds
  `node1`/`node2`/`node3` against your Neon database with no manual
  SQL needed.
- **CORS is wide open** (`allow_origins=["*"]`) - fine for a
  prototype; tighten to your actual frontend's origin in
  `backend/main.py` if you want to lock it down later.
- **Cold starts, twice over**: if both Render's web service and
  Neon's compute have been idle, the very first request after a while
  wakes both up - could take a few seconds total. Requests after that
  are fast until everything goes idle again.

---

## 6. Connect the frontend

If you deployed `frontend/index.html` to Cloudflare Pages (or
anywhere else):

1. Open the deployed frontend page.
2. In the top bar (or the **Settings** page), change the **API base
   URL** from `http://127.0.0.1:8000` to your Render URL, e.g.
   `https://your-app.onrender.com`.
3. CORS already allows it - login/dashboard/files/etc. start working
   immediately. The field isn't persisted (no localStorage, by
   design), so you'd re-enter it each visit unless you hardcode a
   default by editing the `value="http://127.0.0.1:8000"` attributes
   in `frontend/index.html` before deploying it.

---

## Alternatives (with honest caveats)

### Quick demo, no R2/Neon setup - pure Render free tier

Skip steps 1-2 above; use Render's own free Postgres and leave
`STORAGE_BACKEND=local` (edit `render.yaml` to add a `databases:`
block, or create the Postgres addon manually in the dashboard and
paste its connection string as `DATABASE_URL`).

**Real limitations, not hypothetical:** the free Postgres database
is deleted 30 days after creation (14-day grace period to upgrade
first). Uploaded files and registered faces disappear every time the
service spins down from inactivity - in practice, every ~15 minutes
of no traffic. Fine for a five-minute live demo where you register,
upload, and show something working in one sitting. Not fine for
anything you want to still be there tomorrow.

### Railway

Railway no longer has an ongoing free tier - new accounts get a
one-time trial credit, and once that's used up, it's a normal paid
service billed by usage. `railway.json` is still in this repo if you
want to use Railway anyway (e.g. you have credit, or you're fine
paying): connect the repo, add a Postgres plugin (or point it at Neon
the same way as the Render instructions above), set the same
environment variables, and add a volume at `/app/storage` if you use
`STORAGE_BACKEND=local` instead of R2 (Railway's volumes work on its
paid usage-based plan, unlike Render's free tier).

### Pay for it properly

If this stops being a prototype and becomes something with real
users: Render Starter ($7/mo, gets you a real persistent disk if you
prefer `STORAGE_BACKEND=local` over R2) or paid Neon/Render tiers (no
cold starts) are the straightforward next step. R2 itself stays cheap
past the free tier too (no egress fees is the big one).

---

## Cost reality check

Everything in the main path above (Render free + Neon free + R2 free)
is $0/month at this project's scale, with the cold-start tradeoffs
stated above. Prices and free-tier limits change - verify current
numbers on each platform before depending on this for anything beyond
a prototype.
