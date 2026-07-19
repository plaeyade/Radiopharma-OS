"""
Repositorio SQL de usuarios (async).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities import Role, User
from app.infrastructure.db.models import Base, UserRow

# Columnas añadidas tras la primera versión del esquema: se aplican con
# ALTER TABLE si la base ya existe (dev SQLite; en prod va por Alembic).
_MFA_COLUMNS = {
    "mfa_enabled": "BOOLEAN NOT NULL DEFAULT 0",
    "mfa_secret": "VARCHAR(64)",
    "mfa_pending_secret": "VARCHAR(64)",
    "mfa_recovery_json": "VARCHAR(1024) NOT NULL DEFAULT '[]'",
    "mfa_last_step": "INTEGER NOT NULL DEFAULT -1",
}


class SqlUserRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, pool_pre_ping=True)
        self._sf = async_sessionmaker(self._engine, class_=AsyncSession,
                                      expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Migración ligera: añade columnas MFA si la tabla ya existía
            cols = await conn.run_sync(
                lambda c: {col["name"] for col in inspect(c).get_columns("users")})
            for name, ddl in _MFA_COLUMNS.items():
                if name not in cols:
                    await conn.execute(
                        text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))

    async def dispose(self) -> None:
        await self._engine.dispose()

    async def save(self, user: User) -> User:
        async with self._sf() as session:
            session.add(UserRow(
                username=user.username, full_name=user.full_name,
                role=user.role.name.lower(), password_hash=user.password_hash,
                is_active=user.is_active,
                created_at=user.created_at or datetime.now(timezone.utc),
                mfa_enabled=user.mfa_enabled, mfa_secret=user.mfa_secret,
                mfa_pending_secret=user.mfa_pending_secret,
                mfa_recovery_json=json.dumps(list(user.mfa_recovery_hashes)),
                mfa_last_step=user.mfa_last_step))
            await session.commit()
        return user

    async def update(self, user: User) -> User:
        """Actualiza el estado mutable (MFA, activación) de un usuario."""
        async with self._sf() as session:
            row = await session.get(UserRow, user.username)
            if row is None:
                raise KeyError(f"Usuario no encontrado: {user.username}")
            row.full_name = user.full_name
            row.role = user.role.name.lower()
            row.password_hash = user.password_hash
            row.is_active = user.is_active
            row.mfa_enabled = user.mfa_enabled
            row.mfa_secret = user.mfa_secret
            row.mfa_pending_secret = user.mfa_pending_secret
            row.mfa_recovery_json = json.dumps(list(user.mfa_recovery_hashes))
            row.mfa_last_step = user.mfa_last_step
            await session.commit()
        return user

    async def get(self, username: str) -> Optional[User]:
        async with self._sf() as session:
            row = await session.get(UserRow, username)
            return self._to_entity(row) if row else None

    async def list(self) -> list[User]:
        async with self._sf() as session:
            rows = (await session.execute(select(UserRow))).scalars().all()
            return [self._to_entity(r) for r in rows]

    async def count(self) -> int:
        async with self._sf() as session:
            return int((await session.execute(
                select(func.count()).select_from(UserRow))).scalar_one())

    @staticmethod
    def _to_entity(row: UserRow) -> User:
        return User(username=row.username, full_name=row.full_name,
                    role=Role.from_str(row.role), password_hash=row.password_hash,
                    is_active=row.is_active, created_at=row.created_at,
                    mfa_enabled=row.mfa_enabled, mfa_secret=row.mfa_secret,
                    mfa_pending_secret=row.mfa_pending_secret,
                    mfa_recovery_hashes=tuple(
                        json.loads(row.mfa_recovery_json or "[]")),
                    mfa_last_step=row.mfa_last_step)
