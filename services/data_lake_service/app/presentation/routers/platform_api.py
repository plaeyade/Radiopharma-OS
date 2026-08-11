"""API REST del Digital Platform Core (EDS cap. 51)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.platform_core import PlatformCoreEngine, PlataformaInvalida

router = APIRouter(prefix="/api/v1/platform", tags=["platform-core"])
_engine: PlatformCoreEngine | None = None


def init(engine: PlatformCoreEngine | None = None) -> None:
    global _engine
    _engine = engine if engine is not None else PlatformCoreEngine()


def _eng() -> PlatformCoreEngine:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except PlataformaInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class ServicioIn(BaseModel):
    servicio_id: str
    responsabilidad: str
    interfaces: list[str]
    actor: str


class ImagenIn(BaseModel):
    version: str
    dependencias: list[str] = []
    configuracion: dict[str, Any] = {}
    actor: str
    firma: str | None = None


class EstadoServicioIn(BaseModel):
    estado: str
    actor: str
    evidencia: str = ""


class ParametroIn(BaseModel):
    clave: str
    valor: Any
    entorno: str
    vigencia_desde: str
    responsable: str
    motivo: str


@router.post("/services")
def registrar_servicio(body: ServicioIn):
    return _guard(lambda: _eng().registrar_servicio(
        body.servicio_id, body.responsabilidad, body.interfaces, body.actor))


@router.get("/services")
def listar_servicios():
    return _eng().servicios()


@router.post("/services/{servicio_id}/images")
def registrar_imagen(servicio_id: str, body: ImagenIn):
    return _guard(lambda: _eng().registrar_imagen(
        servicio_id, body.version, body.dependencias, body.configuracion,
        body.actor, body.firma))


@router.post("/services/{servicio_id}/estado")
def cambiar_estado(servicio_id: str, body: EstadoServicioIn):
    return _guard(lambda: _eng().cambiar_estado_servicio(
        servicio_id, body.estado, body.actor, body.evidencia))


@router.post("/config")
def definir_parametro(body: ParametroIn):
    return _guard(lambda: _eng().definir_parametro(
        body.clave, body.valor, body.entorno, body.vigencia_desde,
        body.responsable, body.motivo))


@router.get("/config")
def listar_parametros():
    return _eng().listar_parametros()


@router.get("/config/{clave}")
def obtener_parametro(clave: str, entorno: str | None = None, version: int | None = None):
    return _guard(lambda: _eng().parametro(clave, entorno, version))


@router.get("/config/{clave}/historial")
def historial_parametro(clave: str):
    return _guard(lambda: _eng().historial_parametro(clave))


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
