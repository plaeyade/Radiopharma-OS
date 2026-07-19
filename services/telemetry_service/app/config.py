"""
Configuración por entorno del Telemetry Service.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # backend: "sqlite" (dev/test) | "influx" (despliegue)
    backend: str = os.environ.get("TELEMETRY_BACKEND", "sqlite")
    database_url: str = os.environ.get(
        "TELEMETRY_DATABASE_URL", "sqlite+aiosqlite:////tmp/rpos_telemetry.db")
    influx_url: str = os.environ.get("INFLUX_URL", "http://localhost:8086")
    influx_token: str = os.environ.get("INFLUX_TOKEN", "dev-token-change-me")
    influx_org: str = os.environ.get("INFLUX_ORG", "radiopharma")
    influx_bucket: str = os.environ.get("INFLUX_BUCKET", "telemetry")
    jwt_secret: str = os.environ.get(
        "JWT_SECRET", "dev-secret-change-me-in-production")


def load_settings() -> Settings:
    return Settings()
