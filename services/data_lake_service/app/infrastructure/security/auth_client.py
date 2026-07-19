"""
Cliente del Auth Service para re-autenticación de firmas (21 CFR Part 11:
la firma exige verificar las credenciales en el momento de firmar).
"""
from __future__ import annotations

import os

import httpx


class AuthServiceClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._base = (base_url or os.environ.get(
            "AUTH_URL", "http://localhost:8004")).rstrip("/")

    def verify_credentials(self, username: str, password: str) -> bool:
        try:
            with httpx.Client(timeout=5.0) as http:
                r = http.post(f"{self._base}/api/v1/auth/login",
                              json={"username": username, "password": password})
                return r.status_code == 200
        except httpx.HTTPError:
            return False

    def authenticate(self, username: str, password: str) -> dict | None:
        """Re-autenticación completa: login + rol vigente.

        Devuelve {'username': ..., 'role': ...} si las credenciales son
        válidas; None en caso contrario. Implementa AuthVerifier.
        """
        try:
            with httpx.Client(timeout=5.0) as http:
                r = http.post(f"{self._base}/api/v1/auth/login",
                              json={"username": username, "password": password})
                if r.status_code != 200:
                    return None
                token = r.json().get("access_token")
                if not token:
                    return None
                v = http.get(f"{self._base}/api/v1/auth/verify",
                             headers={"Authorization": f"Bearer {token}"})
                if v.status_code != 200:
                    return None
                data = v.json()
                return {"username": data.get("username", username),
                        "role": data.get("role", "operador")}
        except httpx.HTTPError:
            return None

    def get_role(self, token: str) -> str | None:
        try:
            with httpx.Client(timeout=5.0) as http:
                r = http.get(f"{self._base}/api/v1/auth/verify",
                             headers={"Authorization": f"Bearer {token}"})
                if r.status_code == 200:
                    return r.json().get("role")
        except httpx.HTTPError:
            pass
        return None
