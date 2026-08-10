"""Validador OIDC/OAuth2 (cap. 47.7; Informe: OAuth2/OIDC según despliegue).

El Authentication Manager admite múltiples mecanismos conforme a la
política institucional y permanece desacoplado (47.7): la validación
local HMAC convive con la validación de tokens emitidos por un
proveedor OIDC externo (Keycloak en el despliegue de referencia),
verificados contra su JWKS (RS256) con issuer y audiencia.

Honestidad de plataforma: si el proveedor no está configurado, el
estado se reporta y la verificación responde 503 — nunca se acepta
un token sin verificar criptográficamente.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient


class OidcUnavailable(RuntimeError):
    """Proveedor OIDC no configurado o JWKS inalcanzable (→ 503)."""


class OidcTokenInvalido(ValueError):
    """El token no supera la verificación criptográfica (→ 401)."""


@dataclass(frozen=True)
class OidcConfig:
    issuer: str | None
    jwks_url: str | None
    audience: str | None

    @staticmethod
    def from_env() -> "OidcConfig":
        return OidcConfig(
            issuer=os.environ.get("OIDC_ISSUER") or None,
            jwks_url=os.environ.get("OIDC_JWKS_URL") or None,
            audience=os.environ.get("OIDC_AUDIENCE") or None)


class OidcValidator:
    """Verificación de tokens externos contra JWKS del proveedor."""

    def __init__(self, config: OidcConfig | None = None,
                 jwks_client: PyJWKClient | None = None) -> None:
        self._cfg = config or OidcConfig.from_env()
        self._jwks = jwks_client  # inyectable para pruebas

    def status(self) -> dict:
        cfg = self._cfg
        configurado = bool(cfg.issuer and cfg.jwks_url)
        return {"oidc_configurado": configurado,
                "issuer": cfg.issuer,
                "jwks_url": cfg.jwks_url if configurado else None,
                "audience": cfg.audience,
                "nota": "validación desacoplada (47.7): convive con la "
                        "autenticación local; si el proveedor no está "
                        "configurado se reporta honestamente y ningún "
                        "token externo se acepta sin verificación"}

    def verify(self, token: str) -> dict:
        """Verifica firma RS256, issuer, audiencia y expiración."""
        cfg = self._cfg
        if not (cfg.issuer and cfg.jwks_url):
            raise OidcUnavailable(
                "proveedor OIDC no configurado (OIDC_ISSUER/OIDC_JWKS_URL)")
        jwks = self._jwks or PyJWKClient(cfg.jwks_url)
        try:
            key = jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256"], issuer=cfg.issuer,
                audience=cfg.audience,
                options={"require": ["exp", "iat", "iss", "sub"]})
        except OidcUnavailable:
            raise
        except Exception as exc:
            raise OidcTokenInvalido(f"token OIDC inválido: {exc}")
        return {"sub": claims["sub"], "iss": claims["iss"],
                "roles": claims.get("realm_access", {}).get("roles", []),
                "exp": claims["exp"],
                "fuente": "proveedor OIDC externo (Keycloak según despliegue)"}
