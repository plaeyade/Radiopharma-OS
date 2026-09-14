"""API REST de tablas externas de poder de frenado (EDS 19.10).

Único camino honesto para "configurar SRIM": la plataforma nunca lo
ejecuta (software propietario, sin licencia aquí), pero registra tablas
REALES exportadas por el usuario como dato versionado con fuente,
integridad sha256 y estado `registrada_no_calibrada`.

Calibración: compara la tabla externa contra el proveedor activo
(ATIMA versionado) punto a punto con interpolación real; el veredicto
(`calibrada` / `rechazada_declarada`) se registra append-only con
motivo y criterio — nunca se sobrescribe una calibración (ALCOA+).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.application.production_service import ProductionService
from app.infrastructure.stopping.external_tables import (
    ExternalStoppingTables, TablaExternaInvalida)

router = APIRouter(prefix="/api/v1/stopping-power", tags=["stopping"])

_tablas: ExternalStoppingTables | None = None
_service: ProductionService | None = None

# Mapeo declarado material externo → clave del proveedor activo.
MAPEO_MATERIALES = {"agua": "h2o", "h2o": "h2o", "oxigeno": "o2",
                    "nitrogeno": "n2", "zn68": "zn68"}


def init(tablas: ExternalStoppingTables,
         service: ProductionService) -> None:
    global _tablas, _service
    _tablas, _service = tablas, service


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


class CalibracionIn(BaseModel):
    criterio_max_pct: float = 10.0  # desviación máxima aceptable vs proveedor activo
    motivo: str
    registrado_por: str


@router.post("/external-tables/{material}/versions/{version}/calibrate",
             status_code=201)
def calibrar_tabla(material: str, version: int, body: CalibracionIn):
    """Calibración real: tabla externa vs proveedor activo, punto a punto."""
    assert _tablas is not None and _service is not None
    if body.criterio_max_pct <= 0:
        raise HTTPException(422, "el criterio debe ser positivo")
    try:
        entrada = _tablas.obtener(material, version)
        filas = _tablas.leer_filas(entrada)      # verifica sha256 (ALCOA+)
    except TablaExternaInvalida as exc:
        raise HTTPException(404, str(exc)) from exc
    clave = MAPEO_MATERIALES.get(material.strip().lower())
    if clave is None:
        raise HTTPException(
            422, f"sin mapeo declarado de '{material}' al proveedor activo "
            f"— calibración no_demostrable (registrar el mapeo con fuente)")
    try:
        puntos = []
        for e, s_ext in filas:
            s_ref = _service.stopping_power_active(clave, e)
            puntos.append({"energia_mev": e, "externa": s_ext,
                           "referencia": round(s_ref, 4),
                           "desv_pct": round(abs(s_ext - s_ref) / s_ref * 100,
                                             3)})
    except KeyError as exc:
        raise HTTPException(
            503, f"el proveedor activo no cubre '{clave}' — no_demostrable"
        ) from exc
    comparacion = {
        "referencia": _service.stopping_status(),
        "n_puntos": len(puntos),
        "desv_media_pct": round(
            sum(p["desv_pct"] for p in puntos) / len(puntos), 3),
        "desv_max_pct": max(p["desv_pct"] for p in puntos),
        "puntos": puntos,
    }
    try:
        return _tablas.registrar_calibracion(
            material, version, comparacion, body.criterio_max_pct,
            body.motivo, body.registrado_por)
    except TablaExternaInvalida as exc:
        raise HTTPException(422, str(exc)) from exc
