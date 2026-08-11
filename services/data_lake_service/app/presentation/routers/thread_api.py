"""API REST del Digital Thread & Traceability Engine (EDS cap. 58)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.digital_thread import DigitalThreadEngine, HiloInvalido

router = APIRouter(prefix="/api/v1/thread", tags=["digital-thread"])
_engine: DigitalThreadEngine | None = None


def init(engine: DigitalThreadEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else DigitalThreadEngine()


def _eng() -> DigitalThreadEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except HiloInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class HiloIn(BaseModel):
    entidad_id: str
    tipo_entidad: str
    actor: str


class EventoIn(BaseModel):
    dominio: str
    tipo: str
    datos: dict[str, Any] = {}
    actor: str
    timestamp: str | None = None


class LinajeIn(BaseModel):
    dataset_id: str
    origen: str
    actor: str
    transformaciones: list[str] = []
    consumidores: list[str] = []


class EtapaIn(BaseModel):
    etapa: str
    datos: dict[str, Any] = {}
    actor: str


class ActorIn(BaseModel):
    actor: str


class ProcedenciaIn(BaseModel):
    elemento_id: str
    tipo: str
    origen: str
    actor: str
    hash_sha256: str | None = None
    metadatos: dict[str, Any] = {}


@router.post("/threads")
def abrir_hilo(body: HiloIn):
    return _guard(lambda: _eng().abrir_hilo(
        body.entidad_id, body.tipo_entidad, body.actor))


@router.get("/threads/{entidad_id}")
def obtener_hilo(entidad_id: str):
    return _guard(lambda: _eng().hilo(entidad_id))


@router.post("/threads/{entidad_id}/events")
def registrar_evento(entidad_id: str, body: EventoIn):
    return _guard(lambda: _eng().registrar_evento(
        entidad_id, body.dominio, body.tipo, body.datos, body.actor, body.timestamp))


@router.get("/threads/{entidad_id}/reconstruct")
def reconstruir(entidad_id: str, instante: str):
    return _guard(lambda: _eng().reconstruir(entidad_id, instante))


@router.post("/threads/{entidad_id}/correlate")
def correlacionar(entidad_id: str, body: ActorIn):
    return _guard(lambda: _eng().correlacionar(entidad_id, body.actor))


@router.get("/correlations")
def correlaciones(entidad_id: str | None = None):
    return _eng().correlaciones(entidad_id)


@router.post("/lineage")
def registrar_linaje(body: LinajeIn):
    return _guard(lambda: _eng().registrar_linaje(
        body.dataset_id, body.origen, body.actor, body.transformaciones,
        body.consumidores))


@router.get("/lineage/{dataset_id}")
def linaje(dataset_id: str):
    return _guard(lambda: _eng().linaje(dataset_id))


@router.post("/lineage/{dataset_id}/nueva-version")
def nueva_version_linaje(dataset_id: str, body: ActorIn):
    return _guard(lambda: _eng().nueva_version_linaje(dataset_id, body.actor))


@router.post("/genealogy/{lote_id}/etapas")
def registrar_etapa(lote_id: str, body: EtapaIn):
    return _guard(lambda: _eng().registrar_etapa_producto(
        lote_id, body.etapa, body.datos, body.actor))


@router.get("/genealogy/{lote_id}")
def genealogia(lote_id: str):
    return _guard(lambda: _eng().genealogia(lote_id))


@router.post("/provenance")
def registrar_procedencia(body: ProcedenciaIn):
    return _guard(lambda: _eng().registrar_procedencia(
        body.elemento_id, body.tipo, body.origen, body.actor, body.hash_sha256,
        body.metadatos))


@router.get("/provenance/{elemento_id}")
def procedencia(elemento_id: str):
    return _guard(lambda: _eng().procedencia(elemento_id))


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
