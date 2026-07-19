"""
Helpers de test: emisión local de tokens con el secreto de desarrollo.
"""
from __future__ import annotations

import time

import jwt

SECRET = "dev-secret-change-me-in-production"


def make_token(role: str = "operador", sub: str = "test.user") -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "role": role, "iat": now, "exp": now + 3600,
         "iss": "radiopharma-os"},
        SECRET, algorithm="HS256")


def auth_headers(role: str = "operador", sub: str = "test.user") -> dict:
    return {"Authorization": f"Bearer {make_token(role, sub)}"}
