"""API REST de la Biblioteca Universal de Radionúclidos (Informe cap. 19)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.catalogo_canonico import sembrar_catalogo
from app.domain.radionuclide_library import (BibliotecaInvalida,
                                             RadionuclideLibrary)

router = APIRouter(prefix="/api/v1/library", tags=["radionuclide-library"])
_engine: RadionuclideLibrary | None = None


def init(engine: RadionuclideLibrary | None = None,
         sembrar: bool = True) -> None:
    global _engine
    _engine = engine if engine is not None else RadionuclideLibrary()
    if sembrar and not _engine.catalogo():
        sembrar_catalogo(_engine)


def _eng() -> RadionuclideLibrary:
    assert _engine is not None
    return _engine


def _guard(fn):
    try:
        return fn()
    except BibliotecaInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class IncorporacionIn(BaseModel):
    nuclide: str
    categoria: str
    nuclear: dict[str, Any]
    fisica: dict[str, Any]
    quimica: dict[str, Any]
    clinica: dict[str, Any]
    economica: dict[str, Any]
    bibliografia: list[str]
    autor: str
    historial: str = "incorporación inicial"


class DatosExperimentalesIn(BaseModel):
    tipo: str
    datos: list[dict[str, Any]]
    referencia: str
    version_datos: str
    fecha: str
    fuente: str
    autor: str


class EosIn(BaseModel):
    actividad_eob_gbqe: float
    horas_sintesis: float = 0.0


@router.get("/integrations")
def integraciones():
    return _eng().estado_integraciones()


@router.get("/catalog")
def catalogo(categoria: str | None = None):
    return _eng().catalogo(categoria)


@router.post("/nuclides")
def incorporar(body: IncorporacionIn):
    return _guard(lambda: _eng().incorporar(
        body.nuclide, body.categoria, body.nuclear, body.fisica, body.quimica,
        body.clinica, body.economica, body.bibliografia, body.autor,
        body.historial))


@router.get("/nuclides/{nuclide}")
def radionuclido(nuclide: str, version: int | None = None):
    return _guard(lambda: _eng().radionuclido(nuclide, version))


@router.post("/nuclides/{nuclide}/experimental")
def datos_experimentales(nuclide: str, body: DatosExperimentalesIn):
    return _guard(lambda: _eng().registrar_datos_experimentales(
        nuclide, body.tipo, body.datos, body.referencia, body.version_datos,
        body.fecha, body.fuente, body.autor))


@router.get("/nuclides/{nuclide}/experimental")
def listar_experimental(nuclide: str):
    return _guard(lambda: _eng().datos_experimentales(nuclide))


@router.post("/nuclides/{nuclide}/eos")
def eos(nuclide: str, body: EosIn):
    return _guard(lambda: _eng().actividad_eos(
        nuclide, body.actividad_eob_gbqe, body.horas_sintesis))


@router.get("/nuclides/{nuclide}/clinical-window")
def ventana_clinica(nuclide: str):
    return _guard(lambda: _eng().ventana_clinica(nuclide))


@router.get("/audit")
def auditoria():
    return _eng().auditoria()
