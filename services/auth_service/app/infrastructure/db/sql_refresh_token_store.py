"""
Store SQL de refresh tokens (revocación del lado del servidor).
"""
from __future__ import annotations

from datetime import timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities import RefreshToken
from app.infrastructure.db.models import Base, RefreshTokenRow


class SqlRefreshTokenStore:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, pool_pre_ping=True)
        self._sf = async_sessionmaker(self._engine, class_=AsyncSession,
                                      expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self._engine.dispose()

    async def save(self, token: RefreshToken) -> RefreshToken:
        async with self._sf() as session:
            session.add(RefreshTokenRow(
                jti=token.jti, username=token.username,
                issued_at=token.issued_at, expires_at=token.expires_at,
                revoked=token.revoked))
            await session.commit()
        return token

    async def get(self, jti: str) -> Optional[RefreshToken]:
        async with self._sf() as session:
            row = await session.get(RefreshTokenRow, jti)
            return self._to_entity(row) if row else None

    async def revoke(self, jti: str) -> bool:
        async with self._sf() as session:
            result = await session.execute(
                update(RefreshTokenRow)
                .where(RefreshTokenRow.jti == jti,
                       RefreshTokenRow.revoked.is_(False))
                .values(revoked=True))
            await session.commit()
            return result.rowcount > 0

    async def revoke_all_for_user(self, username: str) -> int:
        async with self._sf() as session:
            result = await session.execute(
                update(RefreshTokenRow)
                .where(RefreshTokenRow.username == username,
                       RefreshTokenRow.revoked.is_(False))
                .values(revoked=True))
            await session.commit()
            return int(result.rowcount)

    @staticmethod
    def _to_entity(row: RefreshTokenRow) -> RefreshToken:
        def utc(ts):
            return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
        return RefreshToken(
            jti=row.jti, username=row.username,
            issued_at=utc(row.issued_at), expires_at=utc(row.expires_at),
            revoked=row.revoked)
