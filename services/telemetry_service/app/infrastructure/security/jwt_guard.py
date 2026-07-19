"""
Guard JWT compartido (mismo secreto HS256 de plataforma que Auth/DL).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)
_RANK = {"operador": 1, "supervisor": 2, "calidad": 3, "admin": 4}


@dataclass(frozen=True)
class Identity:
    username: str
    role: str


def current_identity(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Identity:
    if creds is None:
        raise HTTPException(status_code=401, detail="Token requerido")
    secret = os.environ.get("JWT_SECRET", "dev-secret-change-me-in-production")
    try:
        payload = jwt.decode(creds.credentials, secret, algorithms=["HS256"],
                             issuer="radiopharma-os")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Token inválido: {exc}")
    return Identity(username=payload.get("sub", ""),
                    role=payload.get("role", "operador"))


def require_operator(identity: Identity = Depends(current_identity)) -> Identity:
    if _RANK.get(identity.role, 0) < 1:
        raise HTTPException(status_code=403, detail="Rol insuficiente")
    return identity
