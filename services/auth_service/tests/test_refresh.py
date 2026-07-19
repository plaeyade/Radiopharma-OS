"""
Tests de refresh tokens: emisión, rotación, revocación y offboarding.
"""
from __future__ import annotations

import jwt as _jwt
import pytest
from fastapi.testclient import TestClient

from app.infrastructure.security.jwt_issuer import JwtIssuer

SECRET = "test-secret-0123456789abcdef"


# ---------------- seguridad pura ----------------

def test_refresh_roundtrip():
    issuer = JwtIssuer(SECRET)
    token, jti, iat, exp = issuer.issue_refresh("operador.ciclotron", 60)
    claims = issuer.verify_refresh(token)
    assert claims.sub == "operador.ciclotron"
    assert claims.jti == jti
    assert exp - iat == 3600


def test_verify_refresh_rechaza_access_token():
    from app.domain.entities import Role, User
    issuer = JwtIssuer(SECRET)
    access = issuer.issue(User(username="u1", full_name="U Uno",
                               role=Role.OPERADOR, password_hash="x"), 60)
    with pytest.raises(_jwt.InvalidTokenError):
        issuer.verify_refresh(access)


def test_verify_refresh_expira():
    issuer = JwtIssuer(SECRET)
    token, *_ = issuer.issue_refresh("u1", -1)   # ya expirado
    with pytest.raises(_jwt.ExpiredSignatureError):
        issuer.verify_refresh(token)
    # con ignore_expiration pasa (para logout idempotente)
    assert issuer.verify_refresh(token, ignore_expiration=True).sub == "u1"


# ---------------- API ----------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/auth.db")
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-seguro-123")
    import importlib
    import app.config as config
    importlib.reload(config)
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def _login(c, username="admin", password="admin-seguro-123"):
    r = c.post("/api/v1/auth/login",
               json={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()


def test_login_emite_par_access_y_refresh(client):
    body = _login(client)
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in_min"] > 0
    assert body["refresh_expires_in_min"] > 0
    # el access token funciona normal
    v = client.get("/api/v1/auth/verify",
                   headers={"Authorization": f"Bearer {body['access_token']}"})
    assert v.status_code == 200


def test_refresh_rota_y_entrega_nuevo_par(client):
    body = _login(client)
    r = client.post("/api/v1/auth/refresh",
                    json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 200
    nuevo = r.json()
    assert nuevo["access_token"] != body["access_token"]
    assert nuevo["refresh_token"] != body["refresh_token"]
    # el nuevo access token es válido
    v = client.get("/api/v1/auth/verify",
                   headers={"Authorization": f"Bearer {nuevo['access_token']}"})
    assert v.status_code == 200


def test_refresh_usado_queda_revocado(client):
    """Rotación: reusar el refresh token viejo se rechaza (detección de reuso)."""
    body = _login(client)
    client.post("/api/v1/auth/refresh",
                json={"refresh_token": body["refresh_token"]})
    r = client.post("/api/v1/auth/refresh",
                    json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 401


def test_logout_bloquea_refresh_posterior(client):
    body = _login(client)
    r = client.post("/api/v1/auth/logout",
                    json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["revoked"] is True
    r = client.post("/api/v1/auth/refresh",
                    json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 401


def test_refresh_rechaza_access_token(client):
    body = _login(client)
    r = client.post("/api/v1/auth/refresh",
                    json={"refresh_token": body["access_token"]})
    assert r.status_code == 401


def test_refresh_expirado_rechazado(client):
    token, *_ = JwtIssuer(SECRET).issue_refresh("admin", -1)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert r.status_code == 401


def test_logout_token_desconocido(client):
    token, *_ = JwtIssuer(SECRET).issue_refresh("admin", 60)  # no registrado
    r = client.post("/api/v1/auth/logout", json={"refresh_token": token})
    assert r.status_code == 200   # idempotente: revoca por jti aunque no exista


def test_revocacion_masiva_offboarding(client):
    """Admin revoca todas las sesiones de un usuario (§11.10(d))."""
    s1 = _login(client)
    s2 = _login(client)
    token = s1["access_token"]
    r = client.post("/api/v1/auth/users/admin/revoke",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["revoked"] >= 2
    for s in (s1, s2):
        rr = client.post("/api/v1/auth/refresh",
                         json={"refresh_token": s["refresh_token"]})
        assert rr.status_code == 401


def test_revocacion_masiva_requiere_admin(client):
    # crear operador y usar su token
    admin = _login(client)
    client.post("/api/v1/auth/users",
                headers={"Authorization": f"Bearer {admin['access_token']}"},
                json={"username": "op1", "full_name": "Operador Uno",
                      "password": "password123", "role": "operador"})
    op = _login(client, "op1", "password123")
    r = client.post("/api/v1/auth/users/op1/revoke",
                    headers={"Authorization": f"Bearer {op['access_token']}"})
    assert r.status_code == 403
