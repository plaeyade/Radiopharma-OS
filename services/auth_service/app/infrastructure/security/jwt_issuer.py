"""
Emisor/verificador de JWT HS256 (secreto compartido de plataforma).

Los demás servicios verifican tokens localmente con el mismo secreto
(JWT_SECRET), sin llamada de red por petición.
"""
from __future__ import annotations

import time
from uuid import uuid4

import jwt

from app.domain.entities import RefreshClaims, Role, TokenClaims, User

_ISSUER = "radiopharma-os"


class JwtIssuer:
    def __init__(self, secret: str) -> None:
        if len(secret) < 16:
            raise ValueError("JWT_SECRET debe tener al menos 16 caracteres")
        self._secret = secret

    def issue(self, user: User, ttl_minutes: int) -> str:
        now = int(time.time())
        payload = {
            "sub": user.username,
            "role": user.role.name.lower(),
            "jti": uuid4().hex,   # unicidad por emisión (dos tokens nunca iguales)
            "iat": now,
            "exp": now + ttl_minutes * 60,
            "iss": _ISSUER,
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def verify(self, token: str) -> TokenClaims:
        payload = jwt.decode(token, self._secret, algorithms=["HS256"],
                             issuer=_ISSUER)
        return TokenClaims(
            sub=payload["sub"],
            role=Role.from_str(payload["role"]),
            exp=int(payload["exp"]), iat=int(payload["iat"]))

    def issue_refresh(self, username: str,
                      ttl_minutes: int) -> tuple[str, str, int, int]:
        """Emite un refresh token. Devuelve (token, jti, iat, exp)."""
        now = int(time.time())
        jti = uuid4().hex
        payload = {
            "sub": username,
            "jti": jti,
            "type": "refresh",
            "iat": now,
            "exp": now + ttl_minutes * 60,
            "iss": _ISSUER,
        }
        token = jwt.encode(payload, self._secret, algorithm="HS256")
        return token, jti, now, payload["exp"]

    def verify_refresh(self, token: str,
                       ignore_expiration: bool = False) -> RefreshClaims:
        """Verifica un refresh token. Rechaza tokens de acceso (type != refresh)."""
        payload = jwt.decode(token, self._secret, algorithms=["HS256"],
                             issuer=_ISSUER,
                             options={"verify_exp": not ignore_expiration})
        if payload.get("type") != "refresh":
            raise jwt.InvalidTokenError("No es un refresh token")
        return RefreshClaims(
            sub=payload["sub"], jti=payload["jti"],
            exp=int(payload["exp"]), iat=int(payload["iat"]))
