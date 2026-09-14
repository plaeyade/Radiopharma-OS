"""API REST de tablas externas de poder de frenado (EDS 19.10).

Único camino honesto para "configurar SRIM": la plataforma nunca lo
ejecuta (software propietario, sin licencia aquí), pero registra tablas
REALES exportadas por el usuario como dato versionado con fuente,
integridad sha256 y estado `registrada_no_calibrada`.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.infrastructure.stopping.external_tables import (
    ExternalStoppingTables, TablaExternaInvalida)

router = APIRouter(prefix="/api/v1/stopping-power", tags=["stopping"])

_tablas: ExternalStoppingTables | None = None


def init(tablas: ExternalStoppingTables) -> None:
    global _tablas
    _tablas = tablas


class TablaExternaIn(BaseModel):
    material: str
    fuente: str                     # p. ej. "SRIM-2013 ejecutado por el usuario, archivo X"
    ejecutado_en: str               # fecha/entorno de ejecución (trazabilidad)
    descripcion: str = ""
    filas: list[list[float]]        # [[energia_MeV, stopping_MeV_cm2_g], ...]
    registrado_por: str


@router.post("/external-tables", status_code=201)
def registrar_tabla(body: TablaExternaIn):
    assert _tablas is not None
    try:
        return _tablas.registrar(**body.model_dump())
    except TablaExternaInvalida as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/external-tables")
def listar_tablas():
    assert _tablas is not None
    return {"tablas": _tablas.listar(),
            "nota": ("la plataforma nunca ejecuta ni simula SRIM; estas "
                     "tablas son exportaciones reales registradas por el "
                     "usuario y no se usan en cómputo hasta calibración "
                     "explícita")}
