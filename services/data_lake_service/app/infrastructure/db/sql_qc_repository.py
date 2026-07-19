"""
Repositorio SQL de informes QC (append-only).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities import QcRecord
from app.infrastructure.db.models import QcReportRow


class SqlQcRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def save(self, record: QcRecord) -> QcRecord:
        async with self._sf() as session:
            session.add(QcReportRow(
                qc_id=record.qc_id, batch_id=record.batch_id,
                created_at=record.created_at, created_by=record.created_by,
                product=record.product, nuclide=record.nuclide,
                overall_status=record.overall_status,
                rules_json=json.dumps(list(record.rules), ensure_ascii=False),
                half_life_fit_json=(json.dumps(record.half_life_fit, ensure_ascii=False)
                                    if record.half_life_fit else None),
                record_hash=record.record_hash))
            await session.commit()
        return record

    async def list_for_batch(self, batch_id: str) -> list[QcRecord]:
        async with self._sf() as session:
            stmt = (select(QcReportRow).where(QcReportRow.batch_id == batch_id)
                    .order_by(QcReportRow.created_at.desc()))
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_entity(r) for r in rows]

    async def get(self, qc_id: str) -> Optional[QcRecord]:
        async with self._sf() as session:
            row = await session.get(QcReportRow, qc_id)
            return self._to_entity(row) if row else None

    @staticmethod
    def _to_entity(row: QcReportRow) -> QcRecord:
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return QcRecord(
            qc_id=row.qc_id, batch_id=row.batch_id, created_at=created,
            created_by=row.created_by, product=row.product, nuclide=row.nuclide,
            overall_status=row.overall_status,
            rules=tuple(json.loads(row.rules_json)),
            half_life_fit=(json.loads(row.half_life_fit_json)
                           if row.half_life_fit_json else None),
            record_hash=row.record_hash)
