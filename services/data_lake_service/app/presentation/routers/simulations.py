"""
Router de resultados de simulación científica (EDS 4.9, 7.11).

POST /simulations   — registra un resultado (operador+, ALCOA+)
GET  /simulations   — lista por tipo/reacción
GET  /simulations/{id}         — detalle
GET  /simulations/{id}/verify  — verifica el hash de integridad
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.application.simulation_service import SimulationService
from app.infrastructure.security.jwt_guard import (Identity, current_identity,
                                                   require_operator)

router = APIRouter(prefix="/api/v1/simulations", tags=["simulations"])

_service: SimulationService | None = None


def init(service: SimulationService) -> None:
    global _service
    _service = service


class SimulationIn(BaseModel):
    kind: str = Field(..., examples=["elmer_thermal"])
    solver: str = Field(..., examples=["ElmerSolver 26.2 (/opt/elmer)"])
    inputs: dict
    results: dict
    reaction_id: Optional[str] = None
    target_id: Optional[str] = None


class SimulationOut(BaseModel):
    simulation_id: str
    created_at: str
    created_by: str
    kind: str
    solver: str
    reaction_id: Optional[str]
    target_id: Optional[str]
    inputs: dict
    results: dict
    artifact_key: Optional[str]
    record_hash: str


def _out(r) -> SimulationOut:
    return SimulationOut(
        simulation_id=r.simulation_id, created_at=r.created_at.isoformat(),
        created_by=r.created_by, kind=r.kind, solver=r.solver,
        reaction_id=r.reaction_id, target_id=r.target_id,
        inputs=r.inputs, results=r.results, artifact_key=r.artifact_key,
        record_hash=r.record_hash)


@router.post("", response_model=SimulationOut, status_code=201)
async def register(req: SimulationIn,
                   identity: Identity = Depends(require_operator)) -> SimulationOut:
    try:
        record = await _service.register(
            kind=req.kind, solver=req.solver, created_by=identity.username,
            inputs=req.inputs, results=req.results,
            reaction_id=req.reaction_id, target_id=req.target_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _out(record)


@router.get("", response_model=list[SimulationOut])
async def list_simulations(kind: Optional[str] = None,
                           reaction_id: Optional[str] = None,
                           limit: int = Query(100, ge=1, le=1000),
                           _: Identity = Depends(current_identity),
                           ) -> list[SimulationOut]:
    return [_out(r) for r in await _service.list(kind, reaction_id, limit)]


@router.get("/{simulation_id}", response_model=SimulationOut)
async def get_simulation(simulation_id: str,
                         _: Identity = Depends(current_identity)) -> SimulationOut:
    record = await _service.get(simulation_id)
    if record is None:
        raise HTTPException(status_code=404,
                            detail=f"Simulación no encontrada: {simulation_id}")
    return _out(record)


@router.get("/{simulation_id}/verify")
async def verify_simulation(simulation_id: str,
                            _: Identity = Depends(current_identity)) -> dict:
    record = await _service.get(simulation_id)
    if record is None:
        raise HTTPException(status_code=404,
                            detail=f"Simulación no encontrada: {simulation_id}")
    ok = record.compute_hash() == record.record_hash
    return {"simulation_id": simulation_id, "integrity_ok": ok,
            "record_hash": record.record_hash}
