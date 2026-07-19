"""
Guardia JWT del Data Lake Service.

Verifica tokens HS256 emitidos por el Auth Service (secreto compartido).
Reglas de autorización (ALCOA+ "atribuible" + EDS cap. 47):
- registrar lote:  rol >= operador; created_by se toma del token, nunca del payload
- anular lote:     rol >= calidad
- consultar:       cualquier token válido
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)

_MIN_ROLES = {"operador": 1, "supervisor": 2, "calidad": 3, "admin": 4}


@dataclass(frozen=True)
class Identity:
    username: str
    role: str

    def at_least(self, min_role: str) -> bool:
        return _MIN_ROLES.get(self.role, 0) >= _MIN_ROLES[min_role]


def _secret() -> str:
    return os.environ.get("JWT_SECRET", "dev-secret-change-me-in-production")


def current_identity(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Identity:
    if creds is None:
        raise HTTPException(status_code=401, detail="Token requerido")
    try:
        payload = jwt.decode(creds.credentials, _secret(),
                             algorithms=["HS256"], issuer="radiopharma-os")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Token inválido: {exc}")
    # Solo tokens de acceso: los retos MFA y los refresh tokens (claim "type")
    # no son credenciales de API (el rol vendría vacío por omisión)
    if payload.get("type") is not None:
        raise HTTPException(status_code=401,
                            detail="Solo se aceptan tokens de acceso")
    return Identity(username=payload["sub"], role=payload.get("role", ""))


def require_operator(identity: Identity = Depends(current_identity)) -> Identity:
    if not identity.at_least("operador"):
        raise HTTPException(status_code=403, detail="Se requiere rol operador o superior")
    return identity


def require_calidad(identity: Identity = Depends(current_identity)) -> Identity:
    if not identity.at_least("calidad"):
        raise HTTPException(status_code=403, detail="Solo calidad o admin pueden anular lotes")
    return identity
