"""API REST de óptica de haz — líneas ópticas y transporte (EDS 5.9).

La línea óptica (drifts, cuadrupolos, dipolos, colimadores) se registra
versionada por beamline, cada elemento con fuente citada (49.11). El
transporte lo ejecuta TraceWin real vía adaptador: sin runtime → 503
honesto `sin_runtime`, nunca se simula la envolvente del haz.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.beam_optics import (ElementoOptico, LineaOpticaInvalida,
                                    LineaOpticaRegistry)
from app.domain.beamline import BeamlineInvalido, BeamlineRegistry
from app.infrastructure.tracewin.tracewin_runner import (
    TraceWinError, TraceWinUnavailable, transportar)

router = APIRouter(prefix="/api/v1", tags=["beam-optics"])

_lineas: LineaOpticaRegistry | None = None
_beamlines: BeamlineRegistry | None = None

NOTA_TRANSPORTE = (
    "el transporte lo ejecuta TraceWin (CEA) cuando hay runtime "
    "configurado (TRACEWIN_CMD); sin runtime → 503 honesto — la "
    "plataforma nunca simula la envolvente del haz")


def init(lineas: LineaOpticaRegistry, beamlines: BeamlineRegistry) -> None:
    global _lineas, _beamlines
    _lineas, _beamlines = lineas, beamlines


class ElementoIn(BaseModel):
    tipo: str
    nombre: str
    longitud_m: float
    parametros: dict[str, float] = {}
    fuente: str


class LineaIn(BaseModel):
    elementos: list[ElementoIn]
    registrado_por: str
    motivo_version: str = "registro inicial"


class TransporteIn(BaseModel):
    energia_mev: float
    corriente_ma: float
    version: int | None = None


def _linea_dict(lo) -> dict:
    d = asdict(lo)
    d["elementos"] = [dict(e, parametros=dict(e["parametros"]))
                      for e in d["elementos"]]
    return d


@router.post("/beamlines/{beamline_id}/optics", status_code=201)
def registrar_linea(beamline_id: str, body: LineaIn):
    assert _lineas is not None and _beamlines is not None
    try:
        _beamlines.obtener(beamline_id)
    except BeamlineInvalido as exc:
        raise HTTPException(404, str(exc)) from exc
    elementos = [ElementoOptico(
        tipo=e.tipo, nombre=e.nombre, longitud_m=e.longitud_m,
        parametros=tuple(e.parametros.items()), fuente=e.fuente)
        for e in body.elementos]
    try:
        lo = _lineas.registrar(beamline_id, elementos, body.registrado_por,
                               body.motivo_version)
        return _linea_dict(lo)
    except LineaOpticaInvalida as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/beamlines/{beamline_id}/optics")
def obtener_linea(beamline_id: str, version: int | None = None):
    assert _lineas is not None
    try:
        return _linea_dict(_lineas.obtener(beamline_id, version=version))
    except LineaOpticaInvalida as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/beamlines/{beamline_id}/transport")
def transportar_haz(beamline_id: str, body: TransporteIn):
    assert _lineas is not None
    if body.energia_mev <= 0 or body.corriente_ma <= 0:
        raise HTTPException(422, "energía y corriente deben ser positivas")
    try:
        lo = _lineas.obtener(beamline_id, version=body.version)
    except LineaOpticaInvalida as exc:
        raise HTTPException(404, str(exc)) from exc
    try:
        resultado = transportar(lo, body.energia_mev, body.corriente_ma)
    except TraceWinUnavailable as exc:
        raise HTTPException(
            503, {"estado": "sin_runtime", "detalle": str(exc),
                  "nota": NOTA_TRANSPORTE}) from exc
    except TraceWinError as exc:
        raise HTTPException(500, str(exc)) from exc
    return resultado
