"""
Repositorio SQL del registro de lote (append-only).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.domain.entities import (BatchRecord, BatchStatus, BeamParameters,
                                 DatasetLineage, ProductionResults, ReleaseStatus)
from app.infrastructure.db.models import BatchRow


def _as_utc(ts: Optional[datetime]) -> Optional[datetime]:
    if ts is not None and ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


class SqlBatchRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def save(self, record: BatchRecord) -> BatchRecord:
        async with self._sf() as session:
            session.add(self._to_row(record))
            await session.commit()
        return record

    async def get(self, batch_id: str) -> Optional[BatchRecord]:
        async with self._sf() as session:
            row = await session.get(BatchRow, batch_id)
            return self._to_entity(row) if row else None

    async def list(self, reaction_id: Optional[str] = None,
                   limit: int = 100) -> list[BatchRecord]:
        async with self._sf() as session:
            stmt = select(BatchRow).order_by(BatchRow.created_at.desc()).limit(limit)
            if reaction_id:
                stmt = stmt.where(BatchRow.reaction_id == reaction_id)
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_entity(r) for r in rows]

    async def void(self, batch_id: str, reason: str) -> Optional[BatchRecord]:
        """Anulación controlada (única mutación permitida, ALCOA+)."""
        async with self._sf() as session:
            row = await session.get(BatchRow, batch_id)
            if row is None:
                return None
            row.status = BatchStatus.VOIDED.value
            row.void_reason = reason
            await session.commit()
            return self._to_entity(row)

    async def release(self, batch_id: str, decision: str, released_by: str,
                      reason: Optional[str]) -> Optional[BatchRecord]:
        """Transición controlada de liberación (pending -> released|rejected)."""
        async with self._sf() as session:
            row = await session.get(BatchRow, batch_id)
            if row is None:
                return None
            row.release_status = decision
            row.released_by = released_by
            row.release_reason = reason
            row.released_at = datetime.now(timezone.utc)
            await session.commit()
            return self._to_entity(row)

    # ------------------------------------------------------------------
    @staticmethod
    def _to_row(r: BatchRecord) -> BatchRow:
        return BatchRow(
            batch_id=r.batch_id, created_at=r.created_at, created_by=r.created_by,
            reaction_id=r.reaction_id, target_id=r.target_id,
            product_nuclide=r.product_nuclide,
            beam_energy_mev=r.beam.beam_energy_mev, current_ua=r.beam.current_ua,
            irradiation_time_min=r.beam.irradiation_time_min,
            enrichment=r.beam.enrichment,
            saturation_yield_mbq_ua=r.results.saturation_yield_mbq_ua,
            eob_activity_gbq=r.results.eob_activity_gbq,
            eob_activity_gbq_uncertainty=r.results.eob_activity_gbq_uncertainty,
            saturation_factor=r.results.saturation_factor,
            relative_uncertainty=r.results.relative_uncertainty,
            dataset_id=r.lineage.dataset_id,
            dataset_sha256=r.lineage.dataset_sha256,
            stopping_source=r.lineage.stopping_source,
            status=r.status.value, void_reason=r.void_reason,
            artifact_key=r.artifact_key, record_hash=r.record_hash,
            release_status=r.release_status.value, released_by=r.released_by,
            release_reason=r.release_reason, released_at=r.released_at)

    @staticmethod
    def _to_entity(row: BatchRow) -> BatchRecord:
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return BatchRecord(
            batch_id=row.batch_id, created_at=created, created_by=row.created_by,
            reaction_id=row.reaction_id, target_id=row.target_id,
            product_nuclide=row.product_nuclide,
            beam=BeamParameters(
                beam_energy_mev=row.beam_energy_mev, current_ua=row.current_ua,
                irradiation_time_min=row.irradiation_time_min, enrichment=row.enrichment),
            results=ProductionResults(
                saturation_yield_mbq_ua=row.saturation_yield_mbq_ua,
                eob_activity_gbq=row.eob_activity_gbq,
                eob_activity_gbq_uncertainty=row.eob_activity_gbq_uncertainty,
                saturation_factor=row.saturation_factor,
                relative_uncertainty=row.relative_uncertainty),
            lineage=DatasetLineage(
                dataset_id=row.dataset_id, dataset_sha256=row.dataset_sha256,
                stopping_source=row.stopping_source),
            status=BatchStatus(row.status), void_reason=row.void_reason,
            artifact_key=row.artifact_key, record_hash=row.record_hash,
            release_status=ReleaseStatus(getattr(row, "release_status", "pending")),
            released_by=getattr(row, "released_by", None),
            release_reason=getattr(row, "release_reason", None),
            released_at=_as_utc(getattr(row, "released_at", None)))
