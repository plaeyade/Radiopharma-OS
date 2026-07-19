"""
Repositorio SQL de usuarios (async).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities import Role, User
from app.infrastructure.db.models import Base, UserRow


class SqlUserRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, pool_pre_ping=True)
        self._sf = async_sessionmaker(self._engine, class_=AsyncSession,
                                      expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self._engine.dispose()

    async def save(self, user: User) -> User:
        async with self._sf() as session:
            session.add(UserRow(
                username=user.username, full_name=user.full_name,
                role=user.role.name.lower(), password_hash=user.password_hash,
                is_active=user.is_active,
                created_at=user.created_at or datetime.now(timezone.utc)))
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
                    is_active=row.is_active, created_at=row.created_at)
