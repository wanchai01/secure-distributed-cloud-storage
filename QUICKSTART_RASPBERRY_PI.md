# Quick Deploy Checklist — Raspberry Pi

Condensed version of DEPLOY_RASPBERRY_PI.md — just the actions, no
explanation. Read that file if something here doesn't make sense or
fails.

Total time: ~20-30 minutes (most of it is the build). $0 cost, runs
on your own hardware.

---

## ☐ 0. Check your Pi first

```bash
uname -m
```
- [ ] Says `aarch64` → good, continue.
- [ ] Says `armv7l` → **stop**, reinstall with 64-bit Raspberry Pi OS
  first (Bookworm or newer) via Raspberry Pi Imager. 32-bit will try
  to compile OpenCV from source and can fail or take over an hour.

---

## ☐ 1. Install Docker — ~3 min

```bash
curl -sSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```
- [ ] Log out and back in (or reboot)
- [ ] Verify: `docker --version` and `docker compose version`

---

## ☐ 2. Get the project onto the Pi — ~2 min

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```
(or `scp -r secure-distributed-cloud-storage pi@<PI_IP>:~/` from your PC)

---

## ☐ 3. Set env vars — ~2 min

```bash
cp .env.pi.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"
nano .env
```
- [ ] `DB_PASSWORD=` → pick any real password
- [ ] `SECRET_KEY=` → paste the generated value above

---

## ☐ 4. Build and start — ~10-15 min (Pi build time)

```bash
docker compose up -d --build
docker compose logs -f app
```
- [ ] Wait for `[startup] PostgreSQL connection: OK`
- [ ] Wait for `[startup] Schema init: OK`
- [ ] Ctrl+C to stop watching logs (containers keep running)

---

## ☐ 5. Verify — ~2 min

```bash
curl http://localhost:8000/monitor/health
```
- [ ] Returns `{"status":"healthy",...}`

From another device on the same network:
```bash
hostname -I          # run this on the Pi to get its IP
```
```bash
curl http://<PI_IP>:8000/monitor/health    # run this from another device
```
- [ ] Open `http://<PI_IP>:8000/docs` in a browser to confirm Swagger UI loads

---

## ☐ 6. (Optional) Expose to the internet — ~5 min

**Quick test, temporary URL, no domain needed:**
```bash
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared-linux-arm64.deb
cloudflared tunnel --url http://localhost:8000
```
- [ ] Copy the `https://xxxxx.trycloudflare.com` URL it prints — that's your public address

**Permanent, your own domain** (needs a domain on your Cloudflare account):
```bash
cloudflared tunnel login
cloudflared tunnel create cloud-storage
cloudflared tunnel route dns cloud-storage storage.yourdomain.com
```
- [ ] Create `~/.cloudflared/config.yml` (see DEPLOY_RASPBERRY_PI.md step 6 for the exact contents)
```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```
- [ ] Visit `https://storage.yourdomain.com` to confirm

---

## ☐ 7. (Optional) Connect the frontend / make yourself admin

- [ ] In `frontend/index.html`'s API URL field, enter your Pi's address (LAN IP or tunnel URL)
- [ ] Promote a user to admin:
  ```bash
  docker compose exec db psql -U postgres -d cloud_storage -c "UPDATE users SET role='admin' WHERE username='yourusername';"
  ```
- [ ] Log in again so the new token carries `role: admin`

---

**Done.** Runs on your own hardware, no monthly bill, no cold starts
from a PaaS spinning down. Restarts automatically on reboot once
Docker itself is enabled (`sudo systemctl enable docker`).

## If something breaks

| Symptom | Fix |
|---|---|
| Build hangs compiling OpenCV | You're on 32-bit OS — see step 0 |
| Container killed / Pi freezes during build | Out of RAM — add swap (see DEPLOY_RASPBERRY_PI.md "Common issues") |
| `DB_PASSWORD`/`SECRET_KEY` not set error | `.env` missing or not filled in — redo step 3 |
| cloudflared crashes | Pi Zero/1B/2B are known to segfault it — need a Pi 4/5 |
