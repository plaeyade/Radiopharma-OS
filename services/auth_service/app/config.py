"""
Configuración por entorno del Auth Service.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get(
        "AUTH_DATABASE_URL", "sqlite+aiosqlite:////tmp/rpos_auth.db")
    jwt_secret: str = os.environ.get(
        "JWT_SECRET", "dev-secret-change-me-in-production")
    token_ttl_min: int = int(os.environ.get("JWT_TTL_MIN", "480"))
    refresh_ttl_min: int = int(os.environ.get("JWT_REFRESH_TTL_MIN", "720"))
    seed_admin_user: str = os.environ.get("ADMIN_USERNAME", "admin")
    seed_admin_password: str = os.environ.get("ADMIN_PASSWORD", "admin-change-me")


def load_settings() -> Settings:
    return Settings()
