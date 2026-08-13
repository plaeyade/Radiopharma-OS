"""API REST del Event Bus & Message Broker (EDS cap. 52)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.event_bus import EventBusEngine, EventoInvalido

router = APIRouter(prefix="/api/v1/events", tags=["event-bus"])
_engine: EventBusEngine | None = None


def init(engine: EventBusEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else EventBusEngine()


def _eng() -> EventBusEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except EventoInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class TopicoIn(BaseModel):
    topico: str
    dominio: str
    actor: str


class EsquemaIn(BaseModel):
    tipo: str
    campos_requeridos: list[str]
    actor: str


class SuscripcionIn(BaseModel):
    topico: str
    servicio: str
    actor: str


class PublicarIn(BaseModel):
    tipo: str
    topico: str
    productor: str
    payload: dict[str, Any]


class ReprocesarIn(BaseModel):
    actor: str


@router.get("/broker")
def estado_broker():
    return _eng().estado_broker()


class BrokerIn(BaseModel):
    endpoint: str
    actor: str


@router.post("/broker/connect")
def conectar_broker(body: BrokerIn):
    """Conexión REAL al broker MQTT (52.6); el resultado, incluido el
    fallo, se declara honestamente."""
    return _guard(lambda: _eng().conectar_broker(body.endpoint,
                                                 body.actor))


@router.post("/topics")
def crear_topico(body: TopicoIn):
    return _guard(lambda: _eng().crear_topico(body.topico, body.dominio, body.actor))


@router.get("/topics")
def listar_topicos():
    return _eng().topicos()


@router.post("/schemas")
def registrar_esquema(body: EsquemaIn):
    return _guard(lambda: _eng().registrar_esquema(
        body.tipo, body.campos_requeridos, body.actor))


@router.get("/schemas/{tipo}")
def obtener_esquema(tipo: str, version: int | None = None):
    return _guard(lambda: _eng().esquema(tipo, version))


@router.get("/catalog")
def catalogo_eventos():
    return _eng().catalogo_eventos()


@router.post("/subscriptions")
def suscribir(body: SuscripcionIn):
    return _guard(lambda: _eng().suscribir(body.topico, body.servicio, body.actor))


@router.get("/subscriptions")
def listar_suscripciones(topico: str | None = None):
    return _eng().suscripciones(topico)


@router.post("/publish")
def publicar(body: PublicarIn):
    return _guard(lambda: _eng().publicar(
        body.tipo, body.topico, body.productor, body.payload))


@router.get("/history")
def historial_eventos(topico: str | None = None):
    return _eng().historial_eventos(topico)


@router.get("/dead-letters")
def dead_letters(estado: str | None = None):
    return _eng().dead_letters(estado)


@router.post("/dead-letters/{dead_letter_id}/reprocesar")
def reprocesar(dead_letter_id: str, body: ReprocesarIn):
    return _guard(lambda: _eng().reprocesar_dead_letter(dead_letter_id, body.actor))


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
