"""
Backend SQLite de telemetría (desarrollo y tests; InfluxDB en despliegue).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)

from app.domain.entities import TelemetryPoint
from app.infrastructure.db.models import Base, TelemetryRow


class SqliteTelemetryStore:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, pool_pre_ping=True)
        self._sf = async_sessionmaker(self._engine, class_=AsyncSession,
                                      expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self._engine.dispose()

    async def write(self, points: list[TelemetryPoint]) -> int:
        async with self._sf() as session:
            session.add_all([TelemetryRow(
                series=p.series, ts_epoch=p.ts.timestamp(), value=p.value,
                tags_json=json.dumps(p.tags_dict(), sort_keys=True))
                for p in points])
            await session.commit()
        return len(points)

    async def query(self, series: Optional[str] = None,
                    tags: Optional[dict] = None,
                    start: Optional[datetime] = None,
                    end: Optional[datetime] = None,
                    limit: int = 10000) -> list[TelemetryPoint]:
        stmt = select(TelemetryRow).order_by(TelemetryRow.ts_epoch.asc())
        if series:
            stmt = stmt.where(TelemetryRow.series == series)
        if start:
            stmt = stmt.where(TelemetryRow.ts_epoch >= start.timestamp())
        if end:
            stmt = stmt.where(TelemetryRow.ts_epoch <= end.timestamp())
        if tags:
            # filtro por etiquetas en SQL (json_extract): debe ir ANTES del
            # LIMIT — si el límite se aplica primero y los puntos más
            # recientes son de otro lote, el filtro posterior queda vacío.
            for k, v in tags.items():
                stmt = stmt.where(func.json_extract(
                    TelemetryRow.tags_json, f'$."{k}"') == v)
        stmt = stmt.limit(limit)
        async with self._sf() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [self._to_entity(r) for r in rows]

    async def list_series(self) -> list[str]:
        async with self._sf() as session:
            rows = (await session.execute(
                select(TelemetryRow.series).distinct()
                .order_by(TelemetryRow.series))).scalars().all()
            return list(rows)

    async def count(self, series: Optional[str] = None,
                    tags: Optional[dict] = None) -> int:
        if tags:
            return len(await self.query(series=series, tags=tags))
        stmt = select(func.count()).select_from(TelemetryRow)
        if series:
            stmt = stmt.where(TelemetryRow.series == series)
        async with self._sf() as session:
            return int((await session.execute(stmt)).scalar_one())

    @staticmethod
    def _to_entity(row: TelemetryRow) -> TelemetryPoint:
        tags = tuple(sorted(json.loads(row.tags_json).items()))
        return TelemetryPoint(
            series=row.series,
            ts=datetime.fromtimestamp(row.ts_epoch, tz=timezone.utc),
            value=row.value, tags=tags)
