"""
Fábrica de engine/sesiones async (PostgreSQL en despliegue, SQLite en dev/tests).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)

from app.infrastructure.db.models import Base


def build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False, pool_pre_ping=True)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_schema(engine: AsyncEngine) -> None:
    """Crea el esquema si no existe (MVP; Alembic queda como paso siguiente)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
