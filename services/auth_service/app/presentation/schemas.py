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


class VerifyOut(BaseModel):
    sub: str
    role: str
    exp: int
