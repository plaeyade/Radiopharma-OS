"""Pruebas del validador OIDC (47.7): verificación real RS256 contra JWKS."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.infrastructure.security.oidc_validator import (  # noqa: E402
    OidcConfig, OidcTokenInvalido, OidcUnavailable, OidcValidator)
from app.main import app  # noqa: E402

ISSUER = "https://keycloak.example/realms/radiopharma"
JWKS_URL = "https://keycloak.example/realms/radiopharma/protocol/openid-connect/certs"
AUD = "radiopharma-os"


class _FakeJWK:
    def __init__(self, key):
        self.key = key


class _FakeJWKSClient:
    """JWKS inyectado: evita red en pruebas, verificación real RS256."""
    def __init__(self, public_key_pem: bytes):
        self._pem = public_key_pem

    def get_signing_key_from_jwt(self, token: str):
        return _FakeJWK(self._pem)


@pytest.fixture()
def keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv_pem, pub_pem


def _token(priv_pem: bytes, **over) -> str:
    now = int(time.time())
    claims = {"iss": ISSUER, "sub": "fisico.medico", "aud": AUD,
              "iat": now, "exp": now + 600,
              "realm_access": {"roles": ["fisico_medico"]}}
    claims.update(over)
    return jwt.encode(claims, priv_pem, algorithm="RS256")


def test_verificacion_real_rs256(keypair):
    priv, pub = keypair
    v = OidcValidator(OidcConfig(ISSUER, JWKS_URL, AUD),
                      jwks_client=_FakeJWKSClient(pub))
    res = v.verify(_token(priv))
    assert res["sub"] == "fisico.medico"
    assert "fisico_medico" in res["roles"]
    assert "Keycloak" in res["fuente"]


def test_token_firmado_con_otra_clave_rechazado(keypair):
    _, pub = keypair
    otra = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    otra_pem = otra.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    v = OidcValidator(OidcConfig(ISSUER, JWKS_URL, AUD),
                      jwks_client=_FakeJWKSClient(pub))
    with pytest.raises(OidcTokenInvalido):
        v.verify(_token(otra_pem))


def test_issuer_incorrecto_rechazado(keypair):
    priv, pub = keypair
    v = OidcValidator(OidcConfig(ISSUER, JWKS_URL, AUD),
                      jwks_client=_FakeJWKSClient(pub))
    with pytest.raises(OidcTokenInvalido):
        v.verify(_token(priv, iss="https://evil.example"))


def test_token_expirado_rechazado(keypair):
    priv, pub = keypair
    v = OidcValidator(OidcConfig(ISSUER, JWKS_URL, AUD),
                      jwks_client=_FakeJWKSClient(pub))
    pasado = int(time.time()) - 3600
    with pytest.raises(OidcTokenInvalido):
        v.verify(_token(priv, iat=pasado, exp=pasado + 10))


def test_sin_configuracion_503_honesto(monkeypatch):
    for var in ("OIDC_ISSUER", "OIDC_JWKS_URL", "OIDC_AUDIENCE"):
        monkeypatch.delenv(var, raising=False)
    client = TestClient(app)
    st = client.get("/api/v1/auth/oidc/status")
    assert st.status_code == 200
    assert st.json()["oidc_configurado"] is False
    r = client.post("/api/v1/auth/oidc/verify", json={"token": "x.y.z"})
    assert r.status_code == 503
