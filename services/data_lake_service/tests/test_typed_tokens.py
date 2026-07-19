"""
Regresión de seguridad: los retos MFA y los refresh tokens (claim "type")
NO son credenciales de API — solo se aceptan tokens de acceso.
"""
from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "dev-secret-change-me-in-production"


def _typed_token(kind: str, sub: str = "test.user") -> str:
    """Token con claim 'type' (mfa | refresh) firmado con el secreto válido."""
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "type": kind, "jti": "x", "iat": now, "exp": now + 3600,
         "iss": "radiopharma-os"},
        SECRET, algorithm="HS256")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "objects"))
    import importlib
    import app.config as config
    importlib.reload(config)
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def test_reto_mfa_rechazado(client):
    for kind in ("mfa", "refresh"):
        h = {"Authorization": f"Bearer {_typed_token(kind)}"}
        r = client.get("/api/v1/batches", headers=h)
        assert r.status_code == 401, f"type={kind} aceptado en consulta"
        r = client.post("/api/v1/batches/B-X/events",
                        headers=h, json={"action": "test", "detail": "x"})
        assert r.status_code == 401, f"type={kind} aceptado en escritura"


def test_token_de_acceso_sigue_funcionando(client):
    from tests.test_jwt_guard import auth_headers
    r = client.get("/api/v1/batches", headers=auth_headers())
    assert r.status_code == 200
