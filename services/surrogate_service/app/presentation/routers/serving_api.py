"""API REST del conector BentoML (EDS 20.10/20.11) + puente 41.8."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...domain.serving_connector import (
    ServingConnector,
    ServingInvalido,
    SinServidor,
    SERVING_VERSION,
)
from . import ei_api

router = APIRouter(prefix="/api/v1/serving", tags=["bentoml-serving"])

_connector: ServingConnector | None = None


def init(connector: ServingConnector | None = None, **kwargs) -> None:
    global _connector
    _connector = connector or ServingConnector(**kwargs)


def _con() -> ServingConnector:
    if _connector is None:
        init()
    return _connector  # type: ignore[return-value]


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except SinServidor as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ServingInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class ServidorIn(BaseModel):
    servidor_id: str
    endpoint: str
    responsable: str
    ruta_salud: str = "/healthz"


class InferenciaIn(BaseModel):
    ruta: str
    datos: dict
    modelo: str
    version_modelo: str
    usuario: str


class PuenteIn(BaseModel):
    """Registro de un runtime BentoML en el Inference Engine (41.8)."""
    servidor_id: str
    ruta: str
    modelo_id: str
    version_modelo: str
    actor: str


@router.post("/servers", status_code=201)
def registrar_servidor(body: ServidorIn):
    srv = _guard(_con().registrar_servidor, body.servidor_id,
                 body.endpoint, body.responsable, body.ruta_salud)
    return {"servidor_id": srv.servidor_id, "version": srv.version}


@router.get("/servers")
def servidores():
    return _con().servidores()


@router.get("/servers/{servidor_id}/history")
def historial(servidor_id: str):
    return _con().historial_servidor(servidor_id)


@router.post("/servers/{servidor_id}/probe")
def sondear(servidor_id: str, actor: str = "sistema"):
    return _guard(_con().sondear, servidor_id, actor)


@router.post("/servers/{servidor_id}/infer", status_code=201)
def inferir(servidor_id: str, body: InferenciaIn):
    return _guard(_con().inferir, servidor_id, body.ruta, body.datos,
                  body.modelo, body.version_modelo, body.usuario)


@router.post("/bridge/runtime", status_code=201)
def registrar_runtime_puente(body: PuenteIn):
    """Registra el runtime BentoML real en el Inference Engine (41.8);
    el modelo debe estar validado y desplegado (41.20/42.8) — la
    verificación la hace ei_core contra el Model Registry."""
    runtime = _con().runtime_bentoml(body.servidor_id, body.ruta,
                                     body.modelo_id, body.version_modelo)
    eng = ei_api._engine
    if eng is None:
        raise HTTPException(status_code=503,
                            detail="Inference Engine no inicializado")
    try:
        return eng.registrar_runtime(body.modelo_id, body.version_modelo,
                                     runtime, body.actor)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/status")
def estado():
    return _con().estado()


@router.get("/audit")
def auditoria():
    return _con().auditoria()


@router.get("/meta")
def meta():
    return {"version_motor": SERVING_VERSION,
            "nota": ("BentoML Runtime externo real (20.10) e Inference "
                     "API (20.11); sonda GET /healthz e inferencia POST "
                     "reales vía httpx; sin conexión → 503 honesto.")}
