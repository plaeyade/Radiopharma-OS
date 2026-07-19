"""
Regresión de seguridad: los retos MFA y los refresh tokens (claim "type")
NO son credenciales de API; y un token sin rol no asume rol alguno
(antes se le concedía "operador" por defecto — escalada de privilegios).
"""
from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient

SECRET = "dev-secret-change-me-in-production"


def _token(claims: dict) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": "test.user", "iat": now, "exp": now + 3600,
         "iss": "radiopharma-os", **claims},
        SECRET, algorithm="HS256")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEMETRY_BACKEND", "sqlite")
    monkeypatch.setenv("TELEMETRY_DATABASE_URL",
                       f"sqlite+aiosqlite:///{tmp_path}/tel.db")
    import importlib
    import app.config as config
    importlib.reload(config)
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def test_reto_mfa_y_refresh_rechazados(client):
    body = {"points": [{"series": "beam_current_ua",
                        "ts": "2026-07-01T12:00:00Z", "value": 40.0,
                        "tags": {"batch_id": "B-1"}}]}
    for kind in ("mfa", "refresh"):
        h = {"Authorization": f"Bearer {_token({'type': kind})}"}
        r = client.post("/api/v1/telemetry/points", headers=h, json=body)
        assert r.status_code == 401, f"type={kind} aceptado en ingesta"


def test_token_sin_rol_no_es_operador(client):
    """Un access token sin claim de rol no recibe privilegios por defecto."""
    h = {"Authorization": f"Bearer {_token({})}"}
    body = {"points": [{"series": "beam_current_ua",
                        "ts": "2026-07-01T12:00:00Z", "value": 40.0,
                        "tags": {"batch_id": "B-1"}}]}
    r = client.post("/api/v1/telemetry/points", headers=h, json=body)
    assert r.status_code == 403


def test_token_de_acceso_sigue_funcionando(client):
    from tests.test_jwt_guard import auth_headers
    r = client.get("/api/v1/telemetry/series", headers=auth_headers())
    assert r.status_code == 200
