"""
Casos de uso del Auth Service.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

from app.domain import totp
from app.domain.entities import RefreshToken, Role, TokenClaims, User
from app.domain.interfaces import (PasswordHasher, RefreshTokenStore,
                                   TokenIssuer, UserRepository)


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, users: UserRepository, hasher: PasswordHasher,
                 issuer: TokenIssuer, token_ttl_min: int = 480,
                 refresh_store: RefreshTokenStore | None = None,
                 refresh_ttl_min: int = 720) -> None:
        self._users = users
        self._hasher = hasher
        self._issuer = issuer
        self._ttl = token_ttl_min
        self._refresh_store = refresh_store
        self._refresh_ttl = refresh_ttl_min

    async def register_user(self, username: str, full_name: str,
                            password: str, role: str) -> User:
        if len(password) < 8:
            raise AuthError("La contraseña debe tener al menos 8 caracteres")
        existing = await self._users.get(username)
        if existing is not None:
            raise AuthError(f"El usuario ya existe: {username}")
        user = User(
            username=username, full_name=full_name,
            role=Role.from_str(role),
            password_hash=self._hasher.hash(password),
            created_at=datetime.now(timezone.utc))
        return await self._users.save(user)

    async def authenticate(self, username: str, password: str) -> Optional[str]:
        user = await self._users.get(username)
        if user is None or not user.is_active:
            return None
        if not self._hasher.verify(password, user.password_hash):
            return None
        return self._issuer.issue(user, self._ttl)

    # ---------------- refresh tokens (sesiones de vida corta + revocación) --

    async def login(self, username: str, password: str) -> Optional[dict]:
        """Autentica y emite par access+refresh (refresh registrado en servidor).
        Si el usuario tiene MFA activo, devuelve en su lugar un reto parcial
        (mfa_required + mfa_token de 5 min) canjeable en verify_mfa()."""
        user = await self._users.get(username)
        if user is None or not user.is_active:
            return None
        if not self._hasher.verify(password, user.password_hash):
            return None
        if user.mfa_enabled:
            challenge = self._issuer.issue_mfa_challenge(user.username)
            return {"mfa_required": True, "mfa_token": challenge,
                    "expires_in_min": 5}
        return await self._issue_pair(user)

    async def _issue_pair(self, user: User) -> dict:
        access = self._issuer.issue(user, self._ttl)
        if self._refresh_store is None:
            return {"access_token": access, "refresh_token": None,
                    "expires_in_min": self._ttl, "refresh_expires_in_min": None}
        refresh = await self._issue_and_store_refresh(user.username)
        return {"access_token": access, "refresh_token": refresh,
                "expires_in_min": self._ttl,
                "refresh_expires_in_min": self._refresh_ttl}

    async def refresh(self, refresh_token: str) -> Optional[dict]:
        """Rota el refresh token y emite un nuevo par. None si no es válido."""
        if self._refresh_store is None:
            return None
        try:
            claims = self._issuer.verify_refresh(refresh_token)
        except Exception:
            return None
        stored = await self._refresh_store.get(claims.jti)
        if stored is None or stored.revoked:
            return None
        if stored.expires_at.timestamp() < datetime.now(timezone.utc).timestamp():
            return None
        user = await self._users.get(claims.sub)
        if user is None or not user.is_active:
            return None
        # rotación: el token usado queda revocado (detección básica de reuso)
        await self._refresh_store.revoke(claims.jti)
        access = self._issuer.issue(user, self._ttl)
        new_refresh = await self._issue_and_store_refresh(user.username)
        return {"access_token": access, "refresh_token": new_refresh,
                "expires_in_min": self._ttl,
                "refresh_expires_in_min": self._refresh_ttl}

    async def logout(self, refresh_token: str) -> bool:
        """Revoca el refresh token presentado (idempotente)."""
        if self._refresh_store is None:
            return False
        try:
            claims = self._issuer.verify_refresh(refresh_token,
                                                 ignore_expiration=True)
        except Exception:
            return False
        await self._refresh_store.revoke(claims.jti)   # ya revocado: no-op
        return True

    async def revoke_all(self, username: str) -> int:
        """Revoca todas las sesiones de un usuario (offboarding, §11.10(d))."""
        if self._refresh_store is None:
            return 0
        return await self._refresh_store.revoke_all_for_user(username)

    async def _issue_and_store_refresh(self, username: str) -> str:
        token, jti, iat, exp = self._issuer.issue_refresh(username,
                                                          self._refresh_ttl)
        await self._refresh_store.save(RefreshToken(
            jti=jti, username=username,
            issued_at=datetime.fromtimestamp(iat, tz=timezone.utc),
            expires_at=datetime.fromtimestamp(exp, tz=timezone.utc)))
        return token

    def verify_token(self, token: str) -> TokenClaims:
        """Lanza jwt.PyJWTError si el token no es válido o expiró."""
        return self._issuer.verify(token)

    # ---------------- MFA TOTP (RFC 6238) ------------------------------

    async def verify_mfa(self, mfa_token: str, code: str) -> Optional[dict]:
        """Canjea el reto MFA + código (TOTP o de respaldo) por el par completo."""
        try:
            username = self._issuer.verify_mfa_challenge(mfa_token)
        except Exception:
            return None
        user = await self._users.get(username)
        if user is None or not user.is_active or not user.mfa_enabled:
            return None
        ok, updated = self._check_code(user, code)
        if not ok:
            return None
        await self._users.update(updated)
        return await self._issue_pair(updated)

    @staticmethod
    def _check_code(user: User, code: str) -> tuple[bool, User]:
        """Acepta un TOTP (con anti-replay) o un código de respaldo de un
        solo uso. Devuelve (válido, usuario_con_estado_actualizado)."""
        code = code.strip()
        if user.mfa_secret:
            step = totp.verify(user.mfa_secret, code,
                               last_step=user.mfa_last_step)
            if step is not None:
                return True, replace(user, mfa_last_step=step)
        h = totp.hash_recovery(code)
        if h in user.mfa_recovery_hashes:
            remaining = tuple(x for x in user.mfa_recovery_hashes if x != h)
            return True, replace(user, mfa_recovery_hashes=remaining)
        return False, user

    async def mfa_enroll(self, username: str) -> dict:
        """Inicia el enrolamiento: secreto pendiente + URI otpauth://."""
        user = await self._users.get(username)
        if user is None:
            raise AuthError(f"Usuario no encontrado: {username}")
        if user.mfa_enabled:
            raise AuthError("MFA ya está activo; desactívalo antes de re-enrolar")
        secret = totp.new_secret()
        await self._users.update(replace(user, mfa_pending_secret=secret))
        return {"secret": secret,
                "otpauth_uri": totp.otpauth_uri(secret, username)}

    async def mfa_confirm(self, username: str, code: str) -> dict:
        """Confirma el enrolamiento con un código del authenticator y activa
        MFA. Devuelve los códigos de respaldo (se muestran una sola vez)."""
        user = await self._users.get(username)
        if user is None:
            raise AuthError(f"Usuario no encontrado: {username}")
        if not user.mfa_pending_secret:
            raise AuthError("No hay enrolamiento pendiente; llama primero a enroll")
        step = totp.verify(user.mfa_pending_secret, code)
        if step is None:
            raise AuthError("Código incorrecto")
        codes = totp.new_recovery_codes()
        await self._users.update(replace(
            user, mfa_enabled=True, mfa_secret=user.mfa_pending_secret,
            mfa_pending_secret=None, mfa_last_step=step,
            mfa_recovery_hashes=tuple(totp.hash_recovery(c) for c in codes)))
        return {"recovery_codes": codes}

    async def mfa_disable(self, username: str, code: str) -> None:
        """Desactiva MFA presentando un código válido (TOTP o respaldo)."""
        user = await self._users.get(username)
        if user is None:
            raise AuthError(f"Usuario no encontrado: {username}")
        if not user.mfa_enabled:
            raise AuthError("MFA no está activo")
        ok, updated = self._check_code(user, code)
        if not ok:
            raise AuthError("Código incorrecto")
        await self._users.update(replace(
            updated, mfa_enabled=False, mfa_secret=None,
            mfa_pending_secret=None, mfa_recovery_hashes=(), mfa_last_step=-1))

    async def mfa_reset(self, username: str) -> None:
        """Reset administrativo de MFA (p. ej. pérdida del dispositivo)."""
        user = await self._users.get(username)
        if user is None:
            raise AuthError(f"Usuario no encontrado: {username}")
        await self._users.update(replace(
            user, mfa_enabled=False, mfa_secret=None, mfa_pending_secret=None,
            mfa_recovery_hashes=(), mfa_last_step=-1))

    async def list_users(self) -> list[User]:
        return await self._users.list()

    async def ensure_seed_admin(self, username: str, password: str,
                                full_name: str = "Administrador") -> None:
        """Crea el admin inicial si la base está vacía (bootstrap)."""
        if await self._users.count() == 0:
            await self.register_user(username, full_name, password, "admin")
