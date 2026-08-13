"""API REST del ejecutor PQ real (Informe 14.9) — fase 3."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...domain.pq_runner import EjecutorPQ, PQ_RUNNER_VERSION
from ...domain.qualification import CalificacionInvalida, QualificationEngine

router = APIRouter(prefix="/api/v1/qualification/pq", tags=["pq-runner"])

_runner: EjecutorPQ | None = None


def init(runner: EjecutorPQ | None = None, engine=None, **kwargs) -> None:
    global _runner
    if runner is not None:
        _runner = runner
    else:
        _runner = EjecutorPQ(engine or QualificationEngine(), **kwargs)


def _run() -> EjecutorPQ:
    if _runner is None:
        init()
    return _runner  # type: ignore[return-value]


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except CalificacionInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class CriterioIn(BaseModel):
    criterio: str
    url: str
    status_esperado: int = 200
    contiene: str | None = None
    umbral_ms: float | None = None


class ProtocoloPQIn(BaseModel):
    protocolo_id: str
    componente_id: str
    criterios: list[CriterioIn]
    responsable: str
    motivo: str


@router.post("/protocols", status_code=201)
def definir_protocolo(body: ProtocoloPQIn):
    proto = _guard(_run().definir_protocolo, body.protocolo_id,
                   body.componente_id,
                   [c.model_dump() for c in body.criterios],
                   body.responsable, body.motivo)
    return {"protocolo_id": proto["protocolo_id"],
            "version": proto["version"]}


@router.get("/protocols")
def protocolos():
    return _run().protocolos()


class EjecucionIn(BaseModel):
    ejecutor: str


@router.post("/protocols/{protocolo_id}/run", status_code=201)
def ejecutar(protocolo_id: str, body: EjecucionIn):
    return _guard(_run().ejecutar, protocolo_id, body.ejecutor)


@router.get("/audit")
def auditoria():
    return _run().auditoria()


@router.get("/meta")
def meta():
    return {"version_motor": PQ_RUNNER_VERSION,
            **_run().estado_runner()}
