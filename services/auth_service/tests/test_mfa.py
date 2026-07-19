"""
Tests del MFA TOTP (RFC 6238): vectores estándar, anti-replay, códigos de
respaldo y flujo completo de login en dos pasos.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import time

from app.domain import totp

SECRET = "test-secret-0123456789abcdef"

# Semilla ASCII de los vectores RFC 6238 ("12345678901234567890") en base32
RFC_SEED_B32 = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


# ---------------- vectores RFC 6238 (HMAC-SHA1) ----------------

def test_vectores_rfc_6238():
    """Valores de referencia del apéndice B del RFC (truncados a 6 dígitos)."""
    assert totp.totp(RFC_SEED_B32, at_time=59) == "287082"
    assert totp.totp(RFC_SEED_B32, at_time=1111111109) == "081804"
    assert totp.totp(RFC_SEED_B32, at_time=1111111111) == "050471"
    assert totp.totp(RFC_SEED_B32, at_time=1234567890) == "005924"
    assert totp.totp(RFC_SEED_B32, at_time=2000000000) == "279037"


def test_verify_ventana_y_formato():
    t = 1_700_000_000.0
    step = totp.current_step(t)
    # código del paso anterior: aceptado con window=1, rechazado con window=0
    code_prev = totp.hotp(RFC_SEED_B32, step - 1)
    assert totp.verify(RFC_SEED_B32, code_prev, at_time=t) == step - 1
    assert totp.verify(RFC_SEED_B32, code_prev, at_time=t, window=0) is None
    # formato inválido
    assert totp.verify(RFC_SEED_B32, "12345", at_time=t) is None
    assert totp.verify(RFC_SEED_B32, "abcdef", at_time=t) is None
    assert totp.verify(RFC_SEED_B32, "000000", at_time=t) is None


def test_anti_replay():
    t = 1_700_000_000.0
    code = totp.totp(RFC_SEED_B32, at_time=t)
    step = totp.verify(RFC_SEED_B32, code, at_time=t)
    assert step is not None
    # mismo código con last_step registrado → rechazado
    assert totp.verify(RFC_SEED_B32, code, at_time=t, last_step=step) is None


def test_recovery_codes():
    codes = totp.new_recovery_codes()
    assert len(codes) == 8
    assert len(set(codes)) == 8                     # únicos
    assert all(len(c) == 9 and c[4] == "-" for c in codes)
    assert totp.hash_recovery(codes[0]) == totp.hash_recovery(codes[0].lower())
    assert totp.hash_recovery(codes[0]) != totp.hash_recovery(codes[1])


def test_otpauth_uri():
    uri = totp.otpauth_uri("JBSWY3DPEHPK3PXP", "operador.ciclotron")
    assert uri.startswith("otpauth://totp/Radiopharma%20OS:operador.ciclotron")
    assert "secret=JBSWY3DPEHPK3PXP" in uri and "digits=6" in uri
    assert "issuer=Radiopharma%20OS" in uri and " " not in uri


# ---------------- API: flujo completo en dos pasos ----------------

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


def _crear_operador(c) -> str:
    r = c.post("/api/v1/auth/login",
               json={"username": "admin", "password": "admin-seguro-123"})
    admin_tok = r.json()["access_token"]
    r = c.post("/api/v1/auth/users",
               headers={"Authorization": f"Bearer {admin_tok}"},
               json={"username": "op.mfa", "full_name": "Operador MFA",
                     "password": "clave-segura-1", "role": "operador"})
    assert r.status_code == 201
    return admin_tok


def _login(c, username="op.mfa", password="clave-segura-1"):
    return c.post("/api/v1/auth/login",
                  json={"username": username, "password": password})


def _activar_mfa(c) -> tuple[str, list[str]]:
    """Enrola y confirma MFA de op.mfa. Devuelve (secreto, recovery_codes)."""
    tok = _login(c).json()["access_token"]
    r = c.post("/api/v1/auth/mfa/enroll",
               headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    secret = r.json()["secret"]
    assert "otpauth://" in r.json()["otpauth_uri"]
    # el código de confirmación es del paso N-1 (ventana ±1): así el paso
    # actual queda libre para el primer login (anti-replay consume pasos)
    r = c.post("/api/v1/auth/mfa/confirm",
               headers={"Authorization": f"Bearer {tok}"},
               json={"code": totp.totp(secret, at_time=time.time() - 30)})
    assert r.status_code == 200
    codes = r.json()["recovery_codes"]
    assert len(codes) == 8
    return secret, codes


def test_login_sin_mfa_no_pide_codigo(client):
    _crear_operador(client)
    r = _login(client)
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert "mfa_required" not in r.json()


def test_flujo_mfa_completo(client):
    _crear_operador(client)
    secret, _ = _activar_mfa(client)
    # login: ahora pide segundo factor
    r = _login(client)
    assert r.status_code == 200
    d = r.json()
    assert d["mfa_required"] is True and "access_token" not in d
    # el reto NO sirve como token de acceso
    r = client.get("/api/v1/auth/verify",
                   headers={"Authorization": f"Bearer {d['mfa_token']}"})
    assert r.status_code == 401
    # código incorrecto → 401
    r = client.post("/api/v1/auth/mfa/verify",
                    json={"mfa_token": d["mfa_token"], "code": "000000"})
    assert r.status_code == 401
    # código correcto → par completo
    r = client.post("/api/v1/auth/mfa/verify",
                    json={"mfa_token": d["mfa_token"],
                          "code": totp.totp(secret)})
    assert r.status_code == 200
    assert r.json()["access_token"] and r.json()["refresh_token"]


def test_anti_replay_en_login(client):
    _crear_operador(client)
    secret, _ = _activar_mfa(client)
    d = _login(client).json()
    code = totp.totp(secret)
    r = client.post("/api/v1/auth/mfa/verify",
                    json={"mfa_token": d["mfa_token"], "code": code})
    assert r.status_code == 200
    # reusar el MISMO código (mismo paso) con un reto nuevo → rechazado
    d2 = _login(client).json()
    r = client.post("/api/v1/auth/mfa/verify",
                    json={"mfa_token": d2["mfa_token"], "code": code})
    assert r.status_code == 401


def test_codigo_respaldo_un_solo_uso(client):
    _crear_operador(client)
    _, codes = _activar_mfa(client)
    d = _login(client).json()
    r = client.post("/api/v1/auth/mfa/verify",
                    json={"mfa_token": d["mfa_token"], "code": codes[0]})
    assert r.status_code == 200
    d2 = _login(client).json()
    r = client.post("/api/v1/auth/mfa/verify",
                    json={"mfa_token": d2["mfa_token"], "code": codes[0]})
    assert r.status_code == 401                       # ya consumido


def test_disable_mfa(client):
    _crear_operador(client)
    secret, codes = _activar_mfa(client)
    d = _login(client).json()
    r = client.post("/api/v1/auth/mfa/verify",
                    json={"mfa_token": d["mfa_token"], "code": totp.totp(secret)})
    tok = r.json()["access_token"]
    # el paso actual ya lo consumió el verify del login: desactivar con respaldo
    r = client.post("/api/v1/auth/mfa/disable",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"code": codes[0]})
    assert r.status_code == 200 and r.json()["mfa_enabled"] is False
    # login vuelve a ser de un solo paso
    assert "access_token" in _login(client).json()


def test_reset_admin(client):
    admin_tok = _crear_operador(client)
    _activar_mfa(client)
    r = client.post("/api/v1/auth/users/op.mfa/mfa/reset",
                    headers={"Authorization": f"Bearer {admin_tok}"})
    assert r.status_code == 200 and r.json()["mfa_enabled"] is False
    assert "access_token" in _login(client).json()
    # un no-admin no puede resetear
    tok = _login(client).json()["access_token"]
    r = client.post("/api/v1/auth/users/op.mfa/mfa/reset",
                    headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_confirm_sin_enroll_422(client):
    _crear_operador(client)
    tok = _login(client).json()["access_token"]
    r = client.post("/api/v1/auth/mfa/confirm",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"code": "123456"})
    assert r.status_code == 422


def test_confirm_codigo_incorrecto_422(client):
    _crear_operador(client)
    tok = _login(client).json()["access_token"]
    client.post("/api/v1/auth/mfa/enroll",
                headers={"Authorization": f"Bearer {tok}"})
    r = client.post("/api/v1/auth/mfa/confirm",
                    headers={"Authorization": f"Bearer {tok}"},
                    json={"code": "000000"})
    assert r.status_code == 422


def test_users_list_expone_mfa(client):
    admin_tok = _crear_operador(client)
    _activar_mfa(client)
    r = client.get("/api/v1/auth/users",
                   headers={"Authorization": f"Bearer {admin_tok}"})
    estados = {u["username"]: u["mfa_enabled"] for u in r.json()}
    assert estados["op.mfa"] is True
    assert estados["admin"] is False
