"""
Servicio de resultados de simulación científica (EDS 4.9, 7.11).

Organización física (cap. 4.9): los artefactos se guardan bajo
`simulation/<kind>/<id>/` en el object store — p. ej.
`simulation/elmer_thermal/SIM-…/results.json` con los campos canónicos
del cap. 7.11 (temperature, stresses, deformations, heat flux) cuando
el solver los produce.

Integridad ALCOA+: hash SHA-256 del payload canónico, verificable.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.domain.entities import SimulationRecord
from app.domain.interfaces import ObjectStore, SimulationRepository

_KINDS_VALIDOS = {"elmer_thermal", "elmer_thermomechanical", "monte_carlo", "burnup_radial",
                  "thermal_reduced",
                  "talys_excitation"}


class SimulationService:
    def __init__(self, repo: SimulationRepository,
                 store: ObjectStore | None = None) -> None:
        self._repo = repo
        self._store = store

    async def register(self, kind: str, solver: str, created_by: str,
                       inputs: dict, results: dict,
                       reaction_id: Optional[str] = None,
                       target_id: Optional[str] = None) -> SimulationRecord:
        if kind not in _KINDS_VALIDOS:
            raise ValueError(
                f"kind no soportado: {kind} (válidos: {sorted(_KINDS_VALIDOS)})")
        if not isinstance(inputs, dict) or not isinstance(results, dict):
            raise ValueError("inputs y results deben ser objetos JSON")
        if not results:
            raise ValueError("results no puede estar vacío: sin resultados "
                             "no hay nada que persistir (honestidad científica)")
        sim_id = f"SIM-{uuid.uuid4().hex[:12].upper()}"
        record = SimulationRecord(
            simulation_id=sim_id,
            created_at=datetime.now(timezone.utc),
            created_by=created_by, kind=kind, solver=solver,
            reaction_id=reaction_id, target_id=target_id,
            inputs=inputs, results=results)
        record.record_hash = record.compute_hash()
        # EDS 4.9: organización física simulation/<kind>/<id>/
        key = f"simulation/{kind}/{sim_id}/results.json"
        if self._store is not None:
            artifact = json.dumps(record.canonical_payload(), indent=2,
                                  ensure_ascii=False)
            self._store.put(key, artifact.encode("utf-8"))
            record.artifact_key = key
        await self._repo.save(record)
        return record

    async def get(self, simulation_id: str) -> Optional[SimulationRecord]:
        return await self._repo.get(simulation_id)

    async def list(self, kind: Optional[str] = None,
                   reaction_id: Optional[str] = None,
                   limit: int = 100) -> list[SimulationRecord]:
        return await self._repo.list(kind, reaction_id, limit)

    async def verify(self, simulation_id: str) -> bool:
        record = await self._repo.get(simulation_id)
        if record is None:
            return False
        return record.compute_hash() == record.record_hash
