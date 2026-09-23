# Deploying on a Raspberry Pi

Self-hosting is a different situation from Render/cloud PaaS: a Pi
has a **real, persistent SD card/SSD**, so the ephemeral-filesystem
problem that pushed the Render guide toward Cloudflare R2 doesn't
apply here. `STORAGE_BACKEND=local` (the default) is the right
choice - files just live on the Pi.

## Requirements

- **Raspberry Pi 4 or 5**, 4 GB RAM or more recommended. (A 3B+ can
  work for light personal use but Postgres + OpenCV + Python together
  are not tiny; expect things to feel slow.)
- **Raspberry Pi OS, 64-bit** (Bookworm or newer). This matters:
  `opencv-python-headless` ships prebuilt wheels for 64-bit ARM
  (aarch64) on PyPI, but not reliably for 32-bit ARM (armhf) - on a
  32-bit OS, pip may try to *compile OpenCV from source*, which can
  take well over an hour on a Pi and can fail outright if it runs out
  of RAM. Use 64-bit OS and this isn't an issue. Check with:
  ```bash
  uname -m
  # aarch64 = 64-bit, good. armv7l = 32-bit, reinstall the OS.
  ```
- SSH access to the Pi (or a keyboard/monitor on it).

---

## 1. Install Docker

```bash
curl -sSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

Log out and back in (or reboot) for the group change to take effect.
Verify:

```bash
docker --version
docker compose version
```

---

## 2. Get the project onto the Pi

Either clone from GitHub (if you pushed it there already, e.g. for
the Render guide) or copy the folder directly:

```bash
# Option A: git clone
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# Option B: copy from your PC (run this on your PC, not the Pi)
scp -r secure-distributed-cloud-storage pi@<PI_IP_ADDRESS>:~/
```

---

## 3. Configure environment variables

```bash
cp .env.pi.example .env
nano .env
```

Fill in two values:

```
DB_PASSWORD=pick-a-real-password
SECRET_KEY=<paste output of the command below>
```

Generate a real `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

(`docker-compose.yml` reads `DB_PASSWORD` and `SECRET_KEY` from this
`.env` file automatically - no need to edit `docker-compose.yml`
itself.)

---

## 4. Build and start

```bash
docker compose up -d --build
```

First build takes a while on a Pi (compiling/installing dependencies)
- 5-15 minutes depending on your Pi model and SD card speed. Watch
progress with:

```bash
docker compose logs -f app
```

Look for `[startup] PostgreSQL connection: OK` and `[startup] Schema
init: OK` in the logs - that means it's ready.

---

## 5. Verify

From the Pi itself:

```bash
curl http://localhost:8000/monitor/health
```

From another device on the same network (replace with your Pi's
actual IP, find it with `hostname -I` on the Pi):

```bash
curl http://192.168.1.XXX:8000/monitor/health
```

Open `http://192.168.1.XXX:8000/docs` in a browser on your network to
use Swagger UI, or point `frontend/index.html`'s API URL field at
that same address.

---

## 6. (Optional) Expose it to the internet with Cloudflare Tunnel

This is the natural fit for "using Cloudflare" with a self-hosted
Pi: no port forwarding, no exposing your home IP, free HTTPS.

### Quick test (no domain needed, temporary URL)

```bash
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared-linux-arm64.deb

cloudflared tunnel --url http://localhost:8000
```

This prints a random `https://something.trycloudflare.com` URL that
proxies straight to your Pi. Good for testing; the URL changes every
time you restart the command, and it's not meant to be permanent.

### Permanent setup (your own domain, survives reboots)

Requires a domain added to your Cloudflare account.

```bash
cloudflared tunnel login          # opens a browser to authorize
cloudflared tunnel create cloud-storage
cloudflared tunnel route dns cloud-storage storage.yourdomain.com
```

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: cloud-storage
credentials-file: /home/pi/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: storage.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

Run it as a service so it survives reboots:

```bash
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

Now `https://storage.yourdomain.com` reaches your Pi from anywhere,
with HTTPS handled by Cloudflare automatically.

> If your Pi model is a Zero W, 1B, or 2B, some users report
> `cloudflared` segfaulting on those (underpowered for it) - stick to
> a Pi 4/5 for this step.

---

## 7. Keep it running

```bash
# Auto-starts on boot (Docker's `restart: unless-stopped` in
# docker-compose.yml already handles this once Docker itself starts
# on boot, which the get.docker.com installer sets up by default)
sudo systemctl enable docker

# View logs any time
docker compose logs -f

# Stop / restart
docker compose down
docker compose up -d

# Update after pulling new code
git pull
docker compose up -d --build
```

---

## 8. Common issues

**Build fails trying to compile OpenCV from source, or is extremely
slow.** You're likely on 32-bit Raspberry Pi OS - see the Requirements
section above. Reinstall with 64-bit Raspberry Pi OS. If you can't do
that, add piwheels (a package index with prebuilt ARM wheels) as a
fallback by adding this line near the top of the `Dockerfile`, before
`RUN pip install`:
```dockerfile
RUN pip config set global.extra-index-url https://www.piwheels.org/simple
```

**Container gets killed / Pi becomes unresponsive during build.**
Likely out of memory on a Pi with less than 4 GB RAM. Add swap space:
```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=.*/CONF_SWAPSIZE=2048/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

**`docker compose up` says `DB_PASSWORD` or `SECRET_KEY` not set.**
You skipped step 3, or edited the wrong file - make sure `.env`
(not `.env.example`) exists in the same folder as `docker-compose.yml`
and has both values filled in.

**Face verification feels slow.** Haar-cascade detection is
lightweight enough for a Pi 4/5, but still slower than a cloud VM.
A few hundred milliseconds to a couple seconds per request is normal;
if it's much worse, check `docker stats` for CPU/memory pressure from
running Postgres and the app on the same board.

---

## Lighter alternative: no Docker

If your Pi is resource-constrained (e.g. a 2GB Pi 4) and Docker's
overhead is unwelcome, you can run this exactly like the local-dev
instructions in `README.md` Phase 0, just on Raspberry Pi OS instead
of Windows:

```bash
sudo apt update
sudo apt install python3-venv python3-pip postgresql libglib2.0-0 libsm6 libxext6 libxrender1 -y
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo -u postgres createdb cloud_storage
cp .env.example .env
nano .env   # fill in DATABASE_URL (localhost) and SECRET_KEY
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

This skips Docker's image-build overhead entirely at the cost of
managing the Python environment yourself.
