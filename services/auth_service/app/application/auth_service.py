"""
Casos de uso del Auth Service.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

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
        """Autentica y emite par access+refresh (refresh registrado en servidor)."""
        user = await self._users.get(username)
        if user is None or not user.is_active:
            return None
        if not self._hasher.verify(password, user.password_hash):
            return None
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

    async def list_users(self) -> list[User]:
        return await self._users.list()

    async def ensure_seed_admin(self, username: str, password: str,
                                full_name: str = "Administrador") -> None:
        """Crea el admin inicial si la base está vacía (bootstrap)."""
        if await self._users.count() == 0:
            await self.register_user(username, full_name, password, "admin")
