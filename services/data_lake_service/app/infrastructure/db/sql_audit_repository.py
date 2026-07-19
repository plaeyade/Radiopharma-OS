"""
Repositorio SQL de eventos de proceso declarados (append-only).
"""
from __future__ import annotations

from datetime import timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import AuditEventRecord
from app.infrastructure.db.models import AuditEventRow


class SqlAuditEventRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def save(self, event: AuditEventRecord) -> AuditEventRecord:
        async with self._sf() as session:
            session.add(AuditEventRow(
                event_id=event.event_id, batch_id=event.batch_id,
                timestamp=event.timestamp, actor=event.actor,
                action=event.action, detail=event.detail))
            await session.commit()
        return event

    async def list_for_batch(self, batch_id: str) -> list[AuditEventRecord]:
        async with self._sf() as session:
            stmt = (select(AuditEventRow)
                    .where(AuditEventRow.batch_id == batch_id)
                    .order_by(AuditEventRow.timestamp.asc()))
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_entity(r) for r in rows]

    @staticmethod
    def _to_entity(row: AuditEventRow) -> AuditEventRecord:
        ts = row.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return AuditEventRecord(
            event_id=row.event_id, batch_id=row.batch_id, timestamp=ts,
            actor=row.actor, action=row.action, detail=row.detail)
