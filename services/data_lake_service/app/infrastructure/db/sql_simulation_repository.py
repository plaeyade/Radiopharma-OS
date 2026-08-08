"""
Repositorio SQL de resultados de simulación (append-only).
"""
from __future__ import annotations

import json
from datetime import timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.domain.entities import SimulationRecord
from app.infrastructure.db.models import SimulationRow


class SqlSimulationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def save(self, record: SimulationRecord) -> SimulationRecord:
        async with self._sf() as session:
            session.add(self._to_row(record))
            await session.commit()
        return record

    async def get(self, simulation_id: str) -> Optional[SimulationRecord]:
        async with self._sf() as session:
            row = await session.get(SimulationRow, simulation_id)
            return self._to_entity(row) if row else None

    async def list(self, kind: Optional[str] = None,
                   reaction_id: Optional[str] = None,
                   limit: int = 100) -> list[SimulationRecord]:
        async with self._sf() as session:
            stmt = (select(SimulationRow)
                    .order_by(SimulationRow.created_at.desc()).limit(limit))
            if kind:
                stmt = stmt.where(SimulationRow.kind == kind)
            if reaction_id:
                stmt = stmt.where(SimulationRow.reaction_id == reaction_id)
            rows = (await session.execute(stmt)).scalars().all()
            return [self._to_entity(r) for r in rows]

    @staticmethod
    def _to_row(r: SimulationRecord) -> SimulationRow:
        created = r.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return SimulationRow(
            simulation_id=r.simulation_id, created_at=created,
            created_by=r.created_by, kind=r.kind, solver=r.solver,
            reaction_id=r.reaction_id, target_id=r.target_id,
            inputs_json=json.dumps(r.inputs),
            results_json=json.dumps(r.results),
            artifact_key=r.artifact_key, record_hash=r.record_hash)

    @staticmethod
    def _to_entity(row: SimulationRow) -> SimulationRecord:
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return SimulationRecord(
            simulation_id=row.simulation_id, created_at=created,
            created_by=row.created_by, kind=row.kind, solver=row.solver,
            reaction_id=row.reaction_id, target_id=row.target_id,
            inputs=json.loads(row.inputs_json),
            results=json.loads(row.results_json),
            artifact_key=row.artifact_key, record_hash=row.record_hash)
