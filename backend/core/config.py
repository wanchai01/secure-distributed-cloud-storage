"""
Application configuration.

Loads settings from environment variables (via .env). No secrets are
hardcoded here. See .env.example for the required variables.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

# Load .env from project root
load_dotenv()


class Settings:
    """Central place for all environment-driven configuration."""

    APP_NAME: str = os.getenv("APP_NAME", "Secure Distributed Cloud Storage")
    APP_ENV: str = os.getenv("APP_ENV", "development")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # Cosine similarity threshold for face verification (Phase 6).
    # Illustrative default only - not validated against a real face
    # dataset. Tune with your own photos; see README Phase 6.
    FACE_VERIFY_THRESHOLD: float = float(os.getenv("FACE_VERIFY_THRESHOLD", "0.90"))

    # Storage backend for uploaded files + face encodings.
    # "local" (default) - writes to storage/ on disk, exactly as in
    #   Phases 0-9. Correct for local development and any host with a
    #   real persistent filesystem.
    # "r2" - writes to Cloudflare R2 (S3-compatible) instead. Added
    #   for deploying to hosts with an EPHEMERAL filesystem, like
    #   Render's free tier, where local files are wiped on every
    #   restart/spin-down. Not part of the original Phase 1-9 tech
    #   stack - added specifically to solve that deployment problem.
    #   See DEPLOYMENT.md.
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")

    R2_ACCOUNT_ID: str = os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "")

    @property
    def R2_ENDPOINT_URL(self) -> str:
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    def validate(self) -> None:
        """Fail fast if required secrets/config are missing."""
        missing = []
        if not self.DATABASE_URL:
            missing.append("DATABASE_URL")
        if not self.SECRET_KEY or self.SECRET_KEY == "CHANGE_ME":
            missing.append("SECRET_KEY (must not be default CHANGE_ME)")

        if self.STORAGE_BACKEND == "r2":
            if not self.R2_ACCOUNT_ID:
                missing.append("R2_ACCOUNT_ID")
            if not self.R2_ACCESS_KEY_ID:
                missing.append("R2_ACCESS_KEY_ID")
            if not self.R2_SECRET_ACCESS_KEY:
                missing.append("R2_SECRET_ACCESS_KEY")
            if not self.R2_BUCKET_NAME:
                missing.append("R2_BUCKET_NAME")
        elif self.STORAGE_BACKEND not in ("local", "r2"):
            missing.append(
                f"STORAGE_BACKEND must be 'local' or 'r2', got {self.STORAGE_BACKEND!r}"
            )

        if missing:
            raise RuntimeError(
                "Missing/invalid required environment variables: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill in real values."
            )


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance, so .env is only parsed once."""
    settings = Settings()
    return settings


settings = get_settings()
