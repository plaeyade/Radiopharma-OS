"""
Radiopharma OS - Auth Service (Fase 1: seguridad)
Capa de dominio: usuarios, roles y tokens.

Roles y jerarquía (EDS v2.0, cap. 47 IAM):
    admin > calidad > supervisor > operador

ALCOA+ "atribuible": toda acción sobre registros de lote queda ligada
a una identidad autenticada (sub del token), nunca a texto libre.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class Role(IntEnum):
    OPERADOR = 1
    SUPERVISOR = 2
    CALIDAD = 3
    ADMIN = 4

    @classmethod
    def from_str(cls, value: str) -> "Role":
        try:
            return cls[value.strip().upper()]
        except KeyError:
            raise ValueError(f"Rol desconocido: {value}")


@dataclass(frozen=True)
class User:
    username: str
    full_name: str
    role: Role
    password_hash: str
    is_active: bool = True
    created_at: datetime | None = None
    # --- MFA TOTP (RFC 6238) ---
    mfa_enabled: bool = False
    mfa_secret: str | None = None              # activo (tras confirmar)
    mfa_pending_secret: str | None = None      # enrolado, pendiente de confirmar
    mfa_recovery_hashes: tuple[str, ...] = ()  # SHA-256 de códigos de respaldo
    mfa_last_step: int = -1                    # anti-replay: último paso aceptado


@dataclass(frozen=True)
class TokenClaims:
    """Contenido verificado de un JWT de la plataforma."""
    sub: str            # username
    role: Role
    exp: int
    iat: int
    iss: str = "radiopharma-os"


@dataclass(frozen=True)
class RefreshClaims:
    """Contenido verificado de un refresh token (sin rol: solo identidad+jti)."""
    sub: str
    jti: str
    exp: int
    iat: int
    iss: str = "radiopharma-os"


@dataclass(frozen=True)
class RefreshToken:
    """Refresh token registrado del lado del servidor (revocable)."""
    jti: str
    username: str
    issued_at: datetime
    expires_at: datetime
    revoked: bool = False
