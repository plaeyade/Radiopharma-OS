"""API REST de Observability & Monitoring Platform (EDS cap. 55)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.observability import ObservabilityEngine, ObservabilidadInvalida

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])
_engine: ObservabilityEngine | None = None


def init(engine: ObservabilityEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else ObservabilityEngine()


def _eng() -> ObservabilityEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except ObservabilidadInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class MetricaIn(BaseModel):
    nombre: str
    dominio: str
    valor: float
    unidad: str = ""
    origen: str


class LogIn(BaseModel):
    nivel: str
    servicio: str
    origen: str
    mensaje: str
    contexto: dict[str, Any] = {}


class SpanIn(BaseModel):
    trace_id: str
    servicio: str
    operacion: str
    inicio: str
    duracion_ms: float
    span_padre: str | None = None
    error: str | None = None


class PoliticaAlertaIn(BaseModel):
    nombre: str
    metrica: str
    operador: str
    umbral: float
    prioridad: str
    escalamiento_a: str
    actor: str


class CierreAlertaIn(BaseModel):
    actor: str
    motivo: str


@router.get("/aiops")
def estado_aiops():
    return _eng().estado_aiops()


@router.post("/metrics")
def registrar_metrica(body: MetricaIn):
    return _guard(lambda: _eng().registrar_metrica(
        body.nombre, body.dominio, body.valor, body.unidad, body.origen))


@router.get("/metrics")
def metricas(nombre: str | None = None, dominio: str | None = None):
    return _eng().metricas(nombre, dominio)


@router.post("/logs")
def registrar_log(body: LogIn):
    return _guard(lambda: _eng().registrar_log(
        body.nivel, body.servicio, body.origen, body.mensaje, body.contexto))


@router.get("/logs")
def consultar_logs(texto: str | None = None, nivel: str | None = None,
                   servicio: str | None = None):
    return _eng().consultar_logs(texto, nivel, servicio)


@router.post("/traces/spans")
def registrar_span(body: SpanIn):
    return _guard(lambda: _eng().registrar_span(
        body.trace_id, body.servicio, body.operacion, body.inicio,
        body.duracion_ms, body.span_padre, body.error))


@router.get("/traces/{trace_id}")
def reconstruir_traza(trace_id: str):
    return _guard(lambda: _eng().reconstruir_traza(trace_id))


@router.post("/alerts/policies")
def definir_politica(body: PoliticaAlertaIn):
    return _guard(lambda: _eng().definir_politica_alerta(
        body.nombre, body.metrica, body.operador, body.umbral, body.prioridad,
        body.escalamiento_a, body.actor))


@router.get("/alerts")
def alertas(prioridad: str | None = None):
    return _eng().alertas(prioridad)


@router.post("/alerts/{alerta_id}/cerrar")
def cerrar_alerta(alerta_id: str, body: CierreAlertaIn):
    return _guard(lambda: _eng().cerrar_alerta(alerta_id, body.actor, body.motivo))


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
