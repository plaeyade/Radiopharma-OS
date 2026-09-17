"""API del Motor de Costos (Fase 29)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...domain.cost_engine import CostEngine, CorridaCosto

router = APIRouter(prefix="/api/v1/costos", tags=["costos"])
_engine: CostEngine | None = None


def init(engine: CostEngine):
    global _engine
    _engine = engine


def _guard() -> CostEngine:
    if _engine is None:
        raise HTTPException(503, "Motor de costos no inicializado")
    return _engine


class CorridaIn(BaseModel):
    corrida_id: str
    isotopo: str
    ciclotron_id: str
    tarifa_id: str
    t_irradiacion_min: float
    t_standby_min: float
    potencia_haz_kw: float
    proveedor_agua_id: str
    agua_cargada_g: float
    fraccion_recuperada: float
    fuente_reciclaje: str
    actividad_producida_gb: float
    n_dosis: int
    costo_desgaste_mxn: float
    fuente_desgaste: str
    costo_consumibles_mxn: float
    fuente_consumibles: str
    motivo: str
    responsable: str


class EscenarioIn(BaseModel):
    modo: str
    margen_pct: float
    motivo: str


@router.get("/ciclotrones")
def ciclotrones():
    return _guard().ciclotrones()


@router.get("/tarifas")
def tarifas():
    return _guard().tarifas()


@router.get("/proveedores-agua")
def proveedores():
    return _guard().proveedores_agua()


@router.get("/corridas")
def corridas():
    return _guard().corridas()


@router.get("/corridas/{corrida_id}")
def corrida(corrida_id: str):
    r = _guard().corrida(corrida_id)
    if r is None:
        raise HTTPException(404, "corrida no encontrada")
    return r


@router.post("/corridas", status_code=201)
def registrar(body: CorridaIn):
    try:
        return _guard().registrar_corrida(CorridaCosto(**body.model_dump()))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/corridas/{corrida_id}/escenarios", status_code=201)
def escenario(corrida_id: str, body: EscenarioIn):
    try:
        return _guard().escenario_precio(corrida_id, body.modo, body.margen_pct, body.motivo)
    except ValueError as e:
        raise HTTPException(422, str(e))
