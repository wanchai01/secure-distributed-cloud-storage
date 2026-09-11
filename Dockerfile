# Production image for Railway / Render / any Docker host.
# Not used for local development (README Phase 0 uses a plain venv) -
# this exists purely for deployment.

FROM python:3.10-slim

# opencv-python-headless still links against a few shared libraries
# that aren't in the slim base image. Installing them here is more
# reliable than depending on a buildpack to include them.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

# Placeholder storage dirs, only used when STORAGE_BACKEND=local (the
# default). For cloud deployment, set STORAGE_BACKEND=r2 instead (see
# DEPLOYMENT.md) - most hosts' free tiers (e.g. Render) have an
# ephemeral filesystem, so files written here won't survive a
# redeploy/restart/spin-down unless a persistent volume is mounted.
RUN mkdir -p storage/node1 storage/node2 storage/node3 storage/faces

EXPOSE 8000

# $PORT is injected by Railway/Render; falls back to 8000 for `docker run` locally.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
