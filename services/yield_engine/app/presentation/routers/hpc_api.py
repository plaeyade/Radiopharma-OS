"""API REST de HPC & Scientific Computing Platform (EDS cap. 57).

El runtime científico (57.10) se inyecta en el motor; por REST, un
trabajo o flujo sin runtime responde 503 honesto — el resultado NUNCA
se inventa.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.hpc import HpcEngine, HpcInvalido, SinRuntimeCientifico

router = APIRouter(prefix="/api/v1/hpc", tags=["hpc"])
_engine: HpcEngine | None = None


def init(engine: HpcEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else HpcEngine(
        cpu_total=64, memoria_total_gb=256.0)


def _eng() -> HpcEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except SinRuntimeCientifico as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except HpcInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class GpuIn(BaseModel):
    gpu_id: str
    modelo: str
    fabricante: str
    memoria_gb: float
    actor: str


class TrabajoIn(BaseModel):
    usuario: str
    prioridad: int
    cpu: int = 0
    gpu: int = 0
    memoria_gb: float = 0.0
    descripcion: str


class FlujoIn(BaseModel):
    flujo_id: str
    etapas: list[dict[str, Any]]
    actor: str


class ActorIn(BaseModel):
    actor: str


@router.get("/resources")
def recursos():
    return _eng().recursos_disponibles()


@router.post("/gpus")
def registrar_gpu(body: GpuIn):
    return _guard(lambda: _eng().registrar_gpu(
        body.gpu_id, body.modelo, body.fabricante, body.memoria_gb, body.actor))


@router.get("/gpus")
def listar_gpus():
    return _eng().gpus()


@router.post("/jobs")
def planificar(body: TrabajoIn):
    return _guard(lambda: _eng().planificar_trabajo(
        body.usuario, body.prioridad, body.cpu, body.gpu, body.memoria_gb,
        body.descripcion))


@router.get("/jobs")
def trabajos(estado: str | None = None):
    return _eng().trabajos(estado)


@router.get("/jobs/queue")
def cola():
    return _eng().cola_pendiente()


@router.post("/jobs/{trabajo_id}/execute")
def ejecutar(trabajo_id: str):
    runtime = getattr(_eng(), "runtimes", {}).get(trabajo_id)
    return _guard(lambda: _eng().ejecutar_trabajo(trabajo_id, runtime))


@router.post("/workflows")
def definir_flujo(body: FlujoIn):
    etapas = [{k: v for k, v in e.items()} for e in body.etapas]
    return _guard(lambda: _eng().definir_flujo(body.flujo_id, etapas, body.actor))


@router.post("/workflows/{flujo_id}/execute")
def ejecutar_flujo(flujo_id: str, body: ActorIn):
    runtimes = getattr(_eng(), "runtimes_flujo", {}).get(flujo_id, {})
    return _guard(lambda: _eng().ejecutar_flujo(flujo_id, runtimes, body.actor))


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
