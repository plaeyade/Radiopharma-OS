"""
Router REST del Auth Service.
"""
from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.auth_service import AuthError, AuthService
from app.domain.entities import Role
from app.presentation.schemas import (LoginIn, LogoutIn, MfaCodeIn,
                                      MfaConfirmOut, MfaEnrollOut,
                                      MfaStatusOut, MfaVerifyIn, RefreshIn,
                                      RevokeOut, TokenOut, UserCreateIn,
                                      UserOut, VerifyOut)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)

_service: AuthService | None = None


def init(service: AuthService) -> None:
    global _service
    _service = service


def _claims(creds: HTTPAuthorizationCredentials | None):
    if creds is None:
        raise HTTPException(status_code=401, detail="Token requerido")
    try:
        return _service.verify_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Token inválido: {exc}")


def _require_admin(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    c = _claims(creds)
    if c.role < Role.ADMIN:
        raise HTTPException(status_code=403, detail="Se requiere rol admin")
    return c


@router.post("/login")
async def login(payload: LoginIn) -> dict:
    """Emite el par access+refresh. Si el usuario tiene MFA activo devuelve
    en su lugar {mfa_required, mfa_token, expires_in_min}: canjear en /mfa/verify."""
    pair = await _service.login(payload.username, payload.password)
    if pair is None:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return pair


@router.post("/mfa/verify", response_model=TokenOut)
async def mfa_verify(payload: MfaVerifyIn) -> TokenOut:
    """Segundo paso del login: reto MFA + código TOTP (o de respaldo)."""
    pair = await _service.verify_mfa(payload.mfa_token, payload.code)
    if pair is None:
        raise HTTPException(status_code=401, detail="Reto MFA inválido o código incorrecto")
    return TokenOut(**pair)


@router.post("/mfa/enroll", response_model=MfaEnrollOut)
async def mfa_enroll(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> MfaEnrollOut:
    """Inicia el enrolamiento MFA del usuario autenticado (secreto + otpauth://)."""
    c = _claims(creds)
    try:
        r = await _service.mfa_enroll(c.sub)
    except AuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return MfaEnrollOut(**r)


@router.post("/mfa/confirm", response_model=MfaConfirmOut)
async def mfa_confirm(payload: MfaCodeIn,
                      creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> MfaConfirmOut:
    """Confirma el enrolamiento con un código del authenticator. Devuelve los
    códigos de respaldo (se muestran una sola vez)."""
    c = _claims(creds)
    try:
        r = await _service.mfa_confirm(c.sub, payload.code)
    except AuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return MfaConfirmOut(**r)


@router.post("/mfa/disable", response_model=MfaStatusOut)
async def mfa_disable(payload: MfaCodeIn,
                      creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> MfaStatusOut:
    """Desactiva MFA presentando un código válido (TOTP o respaldo)."""
    c = _claims(creds)
    try:
        await _service.mfa_disable(c.sub, payload.code)
    except AuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return MfaStatusOut(username=c.sub, mfa_enabled=False)


@router.post("/users/{username}/mfa/reset", response_model=MfaStatusOut)
async def mfa_reset(username: str,
                    _=Depends(_require_admin)) -> MfaStatusOut:
    """Reset administrativo de MFA (pérdida del dispositivo, offboarding)."""
    try:
        await _service.mfa_reset(username)
    except AuthError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return MfaStatusOut(username=username, mfa_enabled=False)


@router.post("/refresh", response_model=TokenOut)
async def refresh(payload: RefreshIn) -> TokenOut:
    """Rota el refresh token y devuelve un nuevo par access+refresh."""
    pair = await _service.refresh(payload.refresh_token)
    if pair is None:
        raise HTTPException(status_code=401,
                            detail="Refresh token inválido, expirado o revocado")
    return TokenOut(**pair)


@router.post("/logout")
async def logout(payload: LogoutIn) -> dict:
    """Revoca el refresh token presentado (idempotente)."""
    revoked = await _service.logout(payload.refresh_token)
    if not revoked:
        raise HTTPException(status_code=401, detail="Refresh token inválido")
    return {"revoked": True}


@router.post("/users/{username}/revoke", response_model=RevokeOut)
async def revoke_sessions(username: str,
                          _=Depends(_require_admin)) -> RevokeOut:
    """Revoca todas las sesiones activas de un usuario (offboarding)."""
    count = await _service.revoke_all(username)
    return RevokeOut(username=username, revoked=count)


@router.get("/verify", response_model=VerifyOut)
async def verify(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> VerifyOut:
    c = _claims(creds)
    return VerifyOut(sub=c.sub, role=c.role.name.lower(), exp=c.exp)


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(payload: UserCreateIn,
                      _=Depends(_require_admin)) -> UserOut:
    try:
        user = await _service.register_user(
            payload.username, payload.full_name, payload.password, payload.role)
    except AuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return UserOut(username=user.username, full_name=user.full_name,
                   role=user.role.name.lower(), is_active=user.is_active,
                   mfa_enabled=user.mfa_enabled)


@router.get("/users", response_model=list[UserOut])
async def list_users(_=Depends(_require_admin)) -> list[UserOut]:
    users = await _service.list_users()
    return [UserOut(username=u.username, full_name=u.full_name,
                    role=u.role.name.lower(), is_active=u.is_active,
                    mfa_enabled=u.mfa_enabled)
            for u in users]
