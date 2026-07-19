"""
Repositorio SQL de alertas activas (reconocimiento atribuible, ALCOA+).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import Alert
from app.infrastructure.db.models import AlertRow


class SqlAlertRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def save(self, alert: Alert) -> Alert:
        async with self._sf() as session:
            session.add(AlertRow(
                alert_id=alert.alert_id, timestamp=alert.timestamp,
                severity=alert.severity, rule=alert.rule,
                batch_id=alert.batch_id, message=alert.message,
                acked_by=alert.acked_by, acked_at=alert.acked_at))
            await session.commit()
        return alert

    async def get(self, alert_id: str) -> Alert | None:
        async with self._sf() as session:
            row = await session.get(AlertRow, alert_id)
            return self._to_entity(row) if row is not None else None

    async def list(self, severity: str | None = None,
                   only_unacked: bool = False,
                   limit: int = 100) -> list[Alert]:
        async with self._sf() as session:
            stmt = select(AlertRow).order_by(AlertRow.timestamp.desc()).limit(limit)
            if severity is not None:
                stmt = stmt.where(AlertRow.severity == severity)
            if only_unacked:
                stmt = stmt.where(AlertRow.acked_by.is_(None))
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_entity(r) for r in rows]

    async def ack(self, alert_id: str, username: str) -> Alert | None:
        """Marca la alerta como reconocida. Idempotente: si ya lo estaba,
        conserva el primer reconocimiento (ALCOA+: el original prevalece)."""
        async with self._sf() as session:
            row = await session.get(AlertRow, alert_id)
            if row is None:
                return None
            if row.acked_by is None:
                row.acked_by = username
                row.acked_at = datetime.now(timezone.utc)
                await session.commit()
            return self._to_entity(row)

    @staticmethod
    def _to_entity(row: AlertRow) -> Alert:
        ts = row.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ack_at = row.acked_at
        if ack_at is not None and ack_at.tzinfo is None:
            ack_at = ack_at.replace(tzinfo=timezone.utc)
        return Alert(alert_id=row.alert_id, timestamp=ts,
                     severity=row.severity, rule=row.rule,
                     batch_id=row.batch_id, message=row.message,
                     acked_by=row.acked_by, acked_at=ack_at)
