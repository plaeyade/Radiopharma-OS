"""API REST del conector OSRM (routing terrestre real)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...domain.osrm_connector import (
    OSRM_VERSION,
    OsrmConnector,
    OsrmInvalido,
    SinOsrm,
)
from . import logistics_api

router = APIRouter(prefix="/api/v1/osrm", tags=["osrm-routing"])

_connector: OsrmConnector | None = None


def init(connector: OsrmConnector | None = None, **kwargs) -> None:
    global _connector
    _connector = connector or OsrmConnector(**kwargs)


def _con() -> OsrmConnector:
    if _connector is None:
        init()
    return _connector  # type: ignore[return-value]


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except SinOsrm as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except OsrmInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _logistics():
    svc = logistics_api._service
    if svc is None:
        raise HTTPException(status_code=503,
                            detail="Logistics Twin no inicializado")
    return svc


class ServidorIn(BaseModel):
    servidor_id: str
    endpoint: str
    responsable: str
    perfil: str = "driving"


class AccionIn(BaseModel):
    actor: str


@router.post("/servers", status_code=201)
def registrar_servidor(body: ServidorIn):
    srv = _guard(_con().registrar_servidor, body.servidor_id,
                 body.endpoint, body.responsable, body.perfil)
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


@router.get("/servers/{servidor_id}/route")
def ruta_directa(servidor_id: str,
                 lon_o: float = Query(...), lat_o: float = Query(...),
                 lon_d: float = Query(...), lat_d: float = Query(...)):
    return _guard(_con().ruta, servidor_id, lon_o, lat_o, lon_d, lat_d)


@router.post("/servers/{servidor_id}/activate")
def activar(servidor_id: str, body: AccionIn):
    return _guard(_con().activar, servidor_id, _logistics(), body.actor)


@router.post("/deactivate")
def desactivar(body: AccionIn):
    return _guard(_con().desactivar, _logistics(), body.actor)


@router.get("/status")
def estado():
    est = _con().estado()
    svc = logistics_api._service
    if svc is not None:
        est["routing_source_vigente_twin"] = getattr(
            svc.routing, "name", "desconocido")
    return est


@router.get("/audit")
def auditoria():
    return _con().auditoria()


@router.get("/meta")
def meta():
    return {"version_motor": OSRM_VERSION,
            "nota": ("OSRM real (route/table HTTP); al activarse, todas "
                     "las rutas terrestres del Logistics Twin usan OSRM "
                     "y routing_source lo declara en cada resultado.")}
