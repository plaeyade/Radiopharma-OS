"""
Esquemas Pydantic del Auth Service.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_min: int
    refresh_token: Optional[str] = None
    refresh_expires_in_min: Optional[int] = None


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


class RevokeOut(BaseModel):
    username: str
    revoked: int


class UserCreateIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    full_name: str = Field(..., min_length=3, max_length=160)
    password: str = Field(..., min_length=8)
    role: str = Field(..., examples=["operador"])


class UserOut(BaseModel):
    username: str
    full_name: str
    role: str
    is_active: bool
    mfa_enabled: bool = False


class VerifyOut(BaseModel):
    sub: str
    role: str
    exp: int


# --- MFA TOTP (RFC 6238) ---

class MfaRequiredOut(BaseModel):
    """Respuesta de /login cuando el usuario tiene MFA activo."""
    mfa_required: bool = True
    mfa_token: str
    expires_in_min: int


class MfaVerifyIn(BaseModel):
    mfa_token: str
    code: str = Field(..., min_length=6, max_length=9,
                      description="TOTP de 6 dígitos o código de respaldo XXXX-XXXX")


class MfaCodeIn(BaseModel):
    code: str = Field(..., min_length=6, max_length=9)


class MfaEnrollOut(BaseModel):
    secret: str
    otpauth_uri: str


class MfaConfirmOut(BaseModel):
    mfa_enabled: bool = True
    recovery_codes: list[str]


class MfaStatusOut(BaseModel):
    username: str
    mfa_enabled: bool
