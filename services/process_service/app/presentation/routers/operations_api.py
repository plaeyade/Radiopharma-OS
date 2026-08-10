"""Router REST del Operational Twin (Fase 5, Informe 18.9):

  POST /api/v1/inventory/lotes              — registrar lote radiactivo
  POST /api/v1/inventory/lotes/{id}/estado  — cambio de estado auditado
  GET  /api/v1/inventory/lotes              — listado
  GET  /api/v1/inventory/lotes/{id}/stock   — actividad decayada a t
  POST /api/v1/inventory/consumibles        — registrar consumible
  POST /api/v1/inventory/consumir           — consumo con caducidad 22.7
  GET  /api/v1/inventory/consumibles        — listado
  GET  /api/v1/inventory/movimientos        — auditoría 28.24
  POST /api/v1/economics/costeo             — costeo ABC del lote (39.9)
  GET  /api/v1/economics/costeos            — resultados registrados
  GET  /api/v1/economics/radiofarmaco/{rp}  — agregación 39.13
  GET  /api/v1/economics/kpis               — KPI Generator 38.12
  GET  /api/v1/operations/kpis              — indicadores operativos 18.9
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.economic_engine import (ConsumoActividad, EconomiaInvalida,
                                        cargar_catalogo, coste_por_radiofarmaco,
                                        costear_lote, kpis_economicos)
from app.domain.inventory import (Consumible, InventarioInvalido,
                                  InventoryService, LoteRadiactivo)
from app.domain.kpis import kpis_operativos

router = APIRouter(prefix="/api/v1", tags=["operational-twin"])

DATA = Path(__file__).resolve().parents[3] / "data"


class _State:
    def __init__(self) -> None:
        self.inventory = InventoryService()
        self.catalog = cargar_catalogo(DATA / "cost_catalog.json")
        self.costeos: list = []
        self.resultados_qc: list[dict] = []


_state: _State | None = None


def init(state: _State | None = None) -> None:
    global _state
    _state = state or _State()


# ------------------------------------------------------------------ schemas
class LoteIn(BaseModel):
    lote_id: str
    radiopharmaceutical: str
    nuclide: str
    half_life_min: float
    actividad_gbq: float
    referencia_temporal: str
    volumen_ml: float = 0.0
    operador: str
    motivo: str


class EstadoIn(BaseModel):
    estado: str
    operador: str
    motivo: str


class ConsumibleIn(BaseModel):
    item_id: str
    nombre: str
    cantidad: float
    unidad: str
    lote: str = ""
    caducidad: str | None = None
    operador: str
    motivo: str


class ConsumoIn(BaseModel):
    item_id: str
    cantidad: float
    operador: str
    motivo: str
    fecha_lote: date | None = None


class ConsumoActividadIn(BaseModel):
    actividad: str
    unidades_driver: float


class CosteoIn(BaseModel):
    lote_id: str
    radiopharmaceutical: str
    consumos: list[ConsumoActividadIn]
    dosis: int
    actividad_eob_gbq: float
    operador: str
    motivo: str


class QcResultIn(BaseModel):
    lote_id: str
    recomendacion: str


# --------------------------------------------------------------- endpoints
@router.post("/inventory/lotes", status_code=201)
def registrar_lote(payload: LoteIn) -> dict:
    try:
        return _state.inventory.registrar_lote(
            LoteRadiactivo(**payload.model_dump(exclude={"operador", "motivo"})),
            payload.operador, payload.motivo)
    except InventarioInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/inventory/lotes/{lote_id}/estado")
def cambiar_estado(lote_id: str, payload: EstadoIn) -> dict:
    try:
        return _state.inventory.cambiar_estado_lote(
            lote_id, payload.estado, payload.operador, payload.motivo)
    except InventarioInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/inventory/lotes")
def listar_lotes() -> list[dict]:
    return _state.inventory.listar_lotes()


@router.get("/inventory/lotes/{lote_id}/stock")
def stock_lote(lote_id: str, instante: datetime | None = None) -> dict:
    try:
        return _state.inventory.stock_lote(lote_id, instante)
    except InventarioInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/inventory/consumibles", status_code=201)
def registrar_consumible(payload: ConsumibleIn) -> dict:
    try:
        return _state.inventory.registrar_consumible(
            Consumible(**payload.model_dump(exclude={"operador", "motivo"})),
            payload.operador, payload.motivo)
    except InventarioInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/inventory/consumir")
def consumir(payload: ConsumoIn) -> dict:
    try:
        return _state.inventory.consumir(payload.item_id, payload.cantidad,
                                         payload.operador, payload.motivo,
                                         payload.fecha_lote)
    except InventarioInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/inventory/consumibles")
def listar_consumibles() -> list[dict]:
    return _state.inventory.listar_consumibles()


@router.get("/inventory/movimientos")
def movimientos() -> list[dict]:
    return _state.inventory.movimientos()


# ----------------------------------------------------------- economía 38-39
@router.post("/economics/costeo", status_code=201)
def costeo(payload: CosteoIn) -> dict:
    try:
        res = costear_lote(
            _state.catalog, payload.lote_id, payload.radiopharmaceutical,
            [ConsumoActividad(**c.model_dump()) for c in payload.consumos],
            payload.dosis, payload.actividad_eob_gbq, payload.operador,
            payload.motivo)
    except EconomiaInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    _state.costeos.append(res)
    return asdict(res)


@router.get("/economics/costeos")
def costeos() -> list[dict]:
    return [asdict(c) for c in _state.costeos]


@router.get("/economics/radiofarmaco/{radiopharmaceutical}")
def por_radiofarmaco(radiopharmaceutical: str) -> dict:
    try:
        return coste_por_radiofarmaco(_state.costeos, radiopharmaceutical)
    except EconomiaInvalida as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/economics/kpis")
def kpis_eco(precio_dosis: float | None = None) -> dict:
    try:
        return kpis_economicos(_state.costeos, precio_dosis)
    except EconomiaInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/economics/catalogo")
def catalogo() -> dict:
    c = _state.catalog
    return {"catalog_id": c.catalog_id, "version": c.version,
            "moneda": c.moneda, "fuente": c.fuente, "validado": c.validado,
            "actividades": {k: asdict(v) for k, v in c.actividades.items()}}


# ------------------------------------------------------ indicadores (18.9)
@router.post("/operations/qc-result", status_code=201)
def registrar_resultado_qc(payload: QcResultIn) -> dict:
    if payload.recomendacion not in ("liberacion", "rechazo", "revision"):
        raise HTTPException(status_code=422,
                            detail="recomendación inválida (25.12)")
    r = payload.model_dump()
    _state.resultados_qc.append(r)
    return r


@router.get("/operations/kpis")
def kpis_ops() -> dict:
    return kpis_operativos(_state.inventory.listar_lotes(),
                           _state.resultados_qc,
                           [asdict(c) for c in _state.costeos])
