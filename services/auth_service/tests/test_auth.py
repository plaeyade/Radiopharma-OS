"""
Tests del Auth Service: hashing, JWT, login, roles y bootstrap admin.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.security.jwt_issuer import JwtIssuer
from app.infrastructure.security.pbkdf2_hasher import Pbkdf2Hasher
from app.domain.entities import Role, User

SECRET = "test-secret-0123456789abcdef"


# ---------------- seguridad pura ----------------

def test_pbkdf2_hash_y_verify():
    h = Pbkdf2Hasher()
    digest = h.hash("secreto123")
    assert digest.startswith("pbkdf2$100000$")
    assert h.verify("secreto123", digest)
    assert not h.verify("otra", digest)
    # dos hashes de la misma contraseña difieren (salt aleatorio)
    assert h.hash("secreto123") != digest


def test_jwt_issue_y_verify():
    issuer = JwtIssuer(SECRET)
    user = User(username="op1", full_name="Operador Uno",
                role=Role.OPERADOR, password_hash="x")
    token = issuer.issue(user, 60)
    claims = issuer.verify(token)
    assert claims.sub == "op1"
    assert claims.role == Role.OPERADOR


def test_jwt_expira():
    import jwt as _jwt
    issuer = JwtIssuer(SECRET)
    user = User(username="op1", full_name="Op", role=Role.OPERADOR, password_hash="x")
    token = issuer.issue(user, -1)  # ya expirado
    with pytest.raises(_jwt.ExpiredSignatureError):
        issuer.verify(token)


def test_jwt_secreto_largo_obligatorio():
    with pytest.raises(ValueError):
        JwtIssuer("corto")


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


def _token(c, username="admin", password="admin-seguro-123"):
    r = c.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_seed_admin_y_login(client):
    token = _token(client)
    v = client.get("/api/v1/auth/verify",
                   headers={"Authorization": f"Bearer {token}"})
    assert v.status_code == 200
    assert v.json()["sub"] == "admin"
    assert v.json()["role"] == "admin"


def test_login_credenciales_malas(client):
    r = client.post("/api/v1/auth/login",
                    json={"username": "admin", "password": "incorrecta"})
    assert r.status_code == 401


def test_crear_usuario_requiere_admin(client):
    r = client.post("/api/v1/auth/users", json={
        "username": "op1", "full_name": "Operador Uno",
        "password": "password123", "role": "operador"})
    assert r.status_code == 401
    token = _token(client)
    r = client.post("/api/v1/auth/users",
                    headers={"Authorization": f"Bearer {token}"}, json={
                    "username": "op1", "full_name": "Operador Uno",
                    "password": "password123", "role": "operador"})
    assert r.status_code == 201
    assert r.json()["role"] == "operador"


def test_rol_desconocido_rechazado(client):
    token = _token(client)
    r = client.post("/api/v1/auth/users",
                    headers={"Authorization": f"Bearer {token}"}, json={
                    "username": "x1", "full_name": "X Uno",
                    "password": "password123", "role": "superusuario"})
    assert r.status_code == 422


def test_lista_usuarios_solo_admin(client):
    token = _token(client)
    r = client.get("/api/v1/auth/users",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert any(u["username"] == "admin" for u in r.json())
