# Quick Deploy Checklist

Condensed version of DEPLOYMENT.md — just the actions, no explanation.
Read DEPLOYMENT.md if something here doesn't make sense or fails.

Total time: ~15-20 minutes. $0 cost.

---

## ☐ 1. Neon (database) — ~3 min

- [ ] Go to https://neon.tech → sign up
- [ ] **Create a project** (any name/region)
- [ ] Click **Connect** on the dashboard
- [ ] Copy the **Pooled** connection string (hostname has `-pooler` in it)
- [ ] Paste it somewhere safe — you'll need it in step 4

```
postgresql://user:password@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require
```

---

## ☐ 2. Cloudflare R2 (file storage) — ~5 min

- [ ] Go to https://dash.cloudflare.com → sign up
- [ ] **R2 Object Storage** → **Create bucket** → name it `cloud-storage-uploads`
- [ ] Copy your **Account ID** (right side of the R2 overview page)
- [ ] **Manage API Tokens** → **Create API Token**
  - Permission: **Object Read & Write**
  - Scope: your new bucket only
- [ ] Copy and save these 4 values:
  - [ ] Account ID
  - [ ] Access Key ID
  - [ ] Secret Access Key (shown once!)
  - [ ] Bucket Name (`cloud-storage-uploads`)

---

## ☐ 3. Push to GitHub — ~2 min

- [ ] Create an empty repo at https://github.com/new (don't add a README)
- [ ] Run in PowerShell, inside the project folder:

```powershell
cd secure-distributed-cloud-storage
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

- [ ] Refresh the GitHub page — confirm files are there (`backend/`, `Dockerfile`, `render.yaml`, etc.)

---

## ☐ 4. Deploy on Render — ~5 min

- [ ] Go to https://render.com → sign in with GitHub
- [ ] **New** → **Blueprint** → pick your repo
- [ ] Render shows a form asking for 5 values — fill them in:

| Field | Paste this |
|---|---|
| `DATABASE_URL` | the Neon pooled string from step 1 |
| `R2_ACCOUNT_ID` | from step 2 |
| `R2_ACCESS_KEY_ID` | from step 2 |
| `R2_SECRET_ACCESS_KEY` | from step 2 |
| `R2_BUCKET_NAME` | `cloud-storage-uploads` |

- [ ] Click **Apply** → wait for the build to finish (watch the logs)
- [ ] Copy your live URL (e.g. `https://secure-distributed-cloud-storage.onrender.com`)

---

## ☐ 5. Verify it works — ~2 min

```powershell
curl https://YOUR-APP.onrender.com/monitor/health
```

- [ ] Should return `{"status":"healthy","database":"connected",...}`
- [ ] If `database` says `disconnected` → recheck the Neon URL (must be the **pooled** one, must end in `?sslmode=require`)
- [ ] Open `https://YOUR-APP.onrender.com/docs` → try `POST /auth/register`, then `POST /auth/login`, then `POST /files/upload`
- [ ] Check Cloudflare dashboard → R2 → your bucket → confirm a new object appeared under `node1/` (or node2/node3)

---

## ☐ 6. (Optional) Connect the frontend

- [ ] Open your deployed `frontend/index.html` (e.g. on Cloudflare Pages)
- [ ] In the top bar, change the API URL field to `https://YOUR-APP.onrender.com`
- [ ] Register/login should now work against the live backend

---

## ☐ 7. (Optional) Make yourself admin

Neon dashboard → **SQL Editor** → run:

```sql
UPDATE users SET role = 'admin' WHERE username = 'yourusername';
```

Then log in again on the frontend/`/docs` so the new token carries `role: admin`.

---

**Done.** Everything above is free, forever, at this project's scale.
First request after idle time (either Render or Neon spinning back up)
takes a few seconds — normal, not an error.
