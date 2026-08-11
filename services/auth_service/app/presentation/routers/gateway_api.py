"""API REST del API Gateway & Integration Layer (EDS cap. 53)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.gateway import ApiGatewayEngine, GatewayInvalido

router = APIRouter(prefix="/api/v1/gateway", tags=["api-gateway"])
_engine: ApiGatewayEngine | None = None


def init(engine: ApiGatewayEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else ApiGatewayEngine()


def _eng() -> ApiGatewayEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except GatewayInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class ApiIn(BaseModel):
    api_id: str
    version: str
    propietario: str
    documentacion: str
    rutas: list[str]
    actor: str


class VersionIn(BaseModel):
    version: str
    documentacion: str
    rutas: list[str]
    actor: str


class TransicionIn(BaseModel):
    estado: str
    actor: str
    motivo: str


class IntegracionIn(BaseModel):
    integracion_id: str
    tipo: str
    sistema: str
    documentacion: str
    apis: list[str] = []
    actor: str


class PoliticaIn(BaseModel):
    max_solicitudes: int
    ventana_s: int
    actor: str


class SolicitudIn(BaseModel):
    api_id: str
    version: str
    ruta: str
    consumidor: str


@router.get("/proxy")
def estado_proxy():
    return _eng().estado_proxy()


@router.post("/apis")
def registrar_api(body: ApiIn):
    return _guard(lambda: _eng().registrar_api(
        body.api_id, body.version, body.propietario, body.documentacion,
        body.rutas, body.actor))


@router.get("/apis")
def listar_apis(estado: str | None = None):
    return _eng().apis(estado)


@router.post("/apis/{api_id}/versions")
def publicar_version(api_id: str, body: VersionIn):
    return _guard(lambda: _eng().publicar_version(
        api_id, body.version, body.documentacion, body.rutas, body.actor))


@router.post("/apis/{api_id}/transicion")
def transicion_api(api_id: str, body: TransicionIn):
    return _guard(lambda: _eng().transicion_api(
        api_id, body.estado, body.actor, body.motivo))


@router.post("/apis/{api_id}/traffic-policy")
def politica_trafico(api_id: str, body: PoliticaIn):
    return _guard(lambda: _eng().definir_politica_trafico(
        api_id, body.max_solicitudes, body.ventana_s, body.actor))


@router.post("/integrations")
def registrar_integracion(body: IntegracionIn):
    return _guard(lambda: _eng().registrar_integracion(
        body.integracion_id, body.tipo, body.sistema, body.documentacion,
        body.apis, body.actor))


@router.get("/integrations")
def listar_integraciones(tipo: str | None = None):
    return _eng().integraciones(tipo)


@router.post("/validate")
def validar_solicitud(body: SolicitudIn):
    return _guard(lambda: _eng().validar_solicitud(
        body.api_id, body.version, body.ruta, body.consumidor))


@router.get("/interactions")
def interacciones(api_id: str | None = None, consumidor: str | None = None):
    return _eng().interacciones(api_id, consumidor)


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
