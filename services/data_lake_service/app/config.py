"""
Configuración por entorno del Data Lake Service.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # sqlite+aiosqlite:////data/datalake.db  (dev)
    # postgresql+asyncpg://user:pass@postgres:5432/radiopharma  (deploy)
    database_url: str = os.environ.get(
        "DATABASE_URL", "sqlite+aiosqlite:////tmp/rpos_datalake.db")
    storage_backend: str = os.environ.get("STORAGE_BACKEND", "local")  # local | minio
    storage_dir: str = os.environ.get("STORAGE_DIR", "/tmp/rpos_objects")
    minio_endpoint: str = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    minio_access_key: str = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket: str = os.environ.get("MINIO_BUCKET", "radiopharma-batches")
    # Webhook de alertado activo (None = solo persistencia + eBR)
    alert_webhook_url: str | None = os.environ.get("ALERT_WEBHOOK_URL")


def load_settings() -> Settings:
    return Settings()
