"""API REST de beamlines y puestos de blanco (EDS 5.9).

La transmisión de la línea SOLO se registra con fuente citada (medición
o ficha técnica del proveedor): no hay motor de óptica de haces
configurado, así que una pérdida nunca se inventa (49.11). Versionado
que nunca sobrescribe; los puestos de blanco tienen estado operativo.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.beamline import BeamlineInvalido, BeamlineRegistry

router = APIRouter(prefix="/api/v1", tags=["beamline"])

_beamlines: BeamlineRegistry | None = None

NOTA_TRANSMISION = (
    "sin motor de óptica de haces configurado, la transmisión solo se "
    "registra con medición o ficha citada — nunca se inventa (49.11)")


def init(beamlines: BeamlineRegistry) -> None:
    global _beamlines
    _beamlines = beamlines


class BeamlineIn(BaseModel):
    ciclotron_id: str
    nombre: str
    transmision: float              # (0, 1] — solo con fuente citada
    fuente_transmision: str
    registrado_por: str
    motivo_version: str = "registro inicial"


class PuestoIn(BaseModel):
    blanco_id: str
    posicion: str
    estado: str = "activo"


@router.post("/beamlines", status_code=201)
def registrar_beamline(body: BeamlineIn):
    assert _beamlines is not None
    try:
        return asdict(_beamlines.registrar(**body.model_dump()))
    except BeamlineInvalido as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/beamlines")
def listar_beamlines(ciclotron_id: str | None = None):
    assert _beamlines is not None
    return {"beamlines": [asdict(b) for b in _beamlines.listar(ciclotron_id)],
            "nota": NOTA_TRANSMISION}


@router.get("/beamlines/{beamline_id}")
def obtener_beamline(beamline_id: str):
    assert _beamlines is not None
    try:
        return asdict(_beamlines.obtener(beamline_id))
    except BeamlineInvalido as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/beamlines/{beamline_id}/target-positions", status_code=201)
def registrar_puesto(beamline_id: str, body: PuestoIn):
    assert _beamlines is not None
    try:
        return asdict(_beamlines.registrar_puesto(beamline_id,
                                                  **body.model_dump()))
    except BeamlineInvalido as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/beamlines/{beamline_id}/target-positions")
def listar_puestos(beamline_id: str):
    assert _beamlines is not None
    try:
        _beamlines.obtener(beamline_id)
    except BeamlineInvalido as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"puestos": [asdict(p) for p in _beamlines.puestos(beamline_id)]}
