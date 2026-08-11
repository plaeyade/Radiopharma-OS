"""API REST de Deployment Technology Reference y Master Reference
Architecture (EDS caps. 59+60)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.architecture_reference import (ArchitectureReferenceEngine,
                                               ReferenciaInvalida)

router = APIRouter(prefix="/api/v1/architecture", tags=["architecture-reference"])
_engine: ArchitectureReferenceEngine | None = None


def init(engine: ArchitectureReferenceEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else ArchitectureReferenceEngine()


def _eng() -> ArchitectureReferenceEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except ReferenciaInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class DecisionIn(BaseModel):
    capa: str
    tecnologia: str
    estado: str
    justificacion: str
    responsable: str


class FlujoIn(BaseModel):
    etapas: list[str]
    actor: str


@router.get("/tech-layers")
def capas_tecnologicas():
    return _eng().capas_tecnologicas()


@router.post("/tech-decisions")
def decidir(body: DecisionIn):
    return _guard(lambda: _eng().decidir_tecnologia(
        body.capa, body.tecnologia, body.estado, body.justificacion,
        body.responsable))


@router.get("/tech-decisions")
def decisiones(capa: str | None = None):
    return _eng().decisiones(capa)


@router.get("/master-layers")
def capas_maestras():
    return _eng().capas_maestras()


@router.get("/volumes")
def volumenes():
    return _eng().volumenes()


@router.post("/flows/{flujo}")
def definir_flujo(flujo: str, body: FlujoIn):
    return _guard(lambda: _eng().definir_flujo(flujo, body.etapas, body.actor))


@router.get("/flows/{flujo}")
def obtener_flujo(flujo: str):
    return _guard(lambda: _eng().flujo(flujo))


@router.get("/coherence")
def coherencia():
    return _eng().verificar_coherencia()


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
