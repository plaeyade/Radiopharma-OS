"""Router REST del Facility Simulation & Capacity Planning Engine (cap. 37).

  POST /api/v1/simulation/scenarios                 — Scenario Manager 37.6
  GET  /api/v1/simulation/scenarios
  POST /api/v1/simulation/scenarios/{id}/run        — Simulation 37.4/37.21
  GET  /api/v1/simulation/scenarios/{id}/results    — histórico 37.20
  POST /api/v1/simulation/compare                   — What-If 37.11 / 37.10
  POST /api/v1/simulation/scenarios/{id}/propose    — propuesta 37.9 (41.9)
  GET  /api/v1/simulation/audit                     — auditoría 37.23

Los escenarios se ejecutan aislados: nunca alteran la operación real
(37.3). Las propuestas son soporte a la decisión, nunca decisiones.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.capacity_simulation import (CapacitySimulationEngine,
                                            Escenario, EtapaEscenario,
                                            RecursoEscenario,
                                            SimulacionInvalida)

router = APIRouter(prefix="/api/v1/simulation", tags=["capacity-planning"])

_engine: CapacitySimulationEngine | None = None


def init(engine: CapacitySimulationEngine | None = None) -> None:
    global _engine
    _engine = engine or CapacitySimulationEngine()


def _guard(fn, *args):
    try:
        return fn(*args)
    except SimulacionInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/scenarios", status_code=201)
def registrar(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    esc = Escenario(
        escenario_id=payload["escenario_id"],
        descripcion=payload["descripcion"], hipotesis=payload["hipotesis"],
        recursos=[RecursoEscenario(**r) for r in payload["recursos"]],
        etapas=[EtapaEscenario(**e) for e in payload["etapas"]],
        demanda_diaria_lotes=float(payload["demanda_diaria_lotes"]),
        version=payload["version"])
    return _guard(_engine.registrar_escenario, esc, usuario)


@router.get("/scenarios")
def escenarios() -> list[dict]:
    return _engine.escenarios()


@router.post("/scenarios/{escenario_id}/run", status_code=201)
def ejecutar(escenario_id: str, payload: dict | None = None) -> dict:
    usuario = (payload or {}).get("usuario", "sistema")
    return _guard(_engine.ejecutar, escenario_id, usuario)


@router.get("/scenarios/{escenario_id}/results")
def resultados(escenario_id: str) -> list[dict]:
    return _engine.resultados(escenario_id)


@router.post("/compare")
def comparar(payload: dict) -> dict:
    return _guard(_engine.comparar, payload["base"], payload["alternativo"],
                  payload.get("usuario", "sistema"))


@router.post("/scenarios/{escenario_id}/propose", status_code=201)
def proponer(escenario_id: str, payload: dict | None = None) -> dict:
    usuario = (payload or {}).get("usuario", "sistema")
    return _guard(_engine.proponer_redistribucion, escenario_id, usuario)


@router.get("/audit")
def auditoria() -> list[dict]:
    return _engine.auditoria()
