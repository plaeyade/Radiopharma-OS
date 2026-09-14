"""API REST del dominio del ciclotrón (Informe §1558; EDS 5.9).

Registro versionado de aceleradores con fuente citada obligatoria e
irradiaciones append-only validadas contra los límites reales de la
máquina, con cálculo EOB del Yield Engine.

Nota de honestidad física: la energía del haz es la declarada en la
corrida; la degradación en la ventana del blanco (19.10 — cadena
SRIM/PSTAR) NO se aplica todavía, por lo que la actividad EOB calculada
es una COTA SUPERIOR declarada, nunca un valor medido.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application.production_service import ProductionService
from app.domain.cyclotron import (CiclotronInvalido, CiclotronRegistry)

router = APIRouter(prefix="/api/v1", tags=["cyclotron"])

_registry: CiclotronRegistry | None = None
_service: ProductionService | None = None

NOTA_COTA_SUPERIOR = (
    "energía de haz declarada en la corrida; la degradación en ventana "
    "(19.10, cadena SRIM/PSTAR) no se aplica aún — EOB = cota superior "
    "declarada, nunca valor medido")


def init(service: ProductionService,
         registry: CiclotronRegistry | None = None) -> None:
    global _registry, _service
    _service = service
    _registry = registry or CiclotronRegistry()


def _reg() -> CiclotronRegistry:
    if _registry is None:
        raise HTTPException(503, "registro de ciclotrones no inicializado")
    return _registry


class CiclotronIn(BaseModel):
    fabricante: str
    modelo: str
    energia_max_mev: float = Field(gt=0)
    corriente_max_ua: float = Field(gt=0)
    estado_operativo: str = "operativo"
    fuente: str                      # referencia citada — obligatoria
    registrado_por: str
    motivo_version: str = "registro inicial"


class IrradiacionIn(BaseModel):
    energia_mev: float = Field(gt=0)
    corriente_ua: float = Field(gt=0)
    tiempo_min: float = Field(gt=0)
    reaccion_id: str = "o18_p_n_f18"
    blanco_id: str = "h2_18o"


def _ciclotron_dict(c) -> dict:
    return dict(ciclotron_id=c.ciclotron_id, fabricante=c.fabricante,
                modelo=c.modelo, energia_max_mev=c.energia_max_mev,
                corriente_max_ua=c.corriente_max_ua,
                estado_operativo=c.estado_operativo, fuente=c.fuente,
                version=c.version, motivo_version=c.motivo_version,
                registrado_por=c.registrado_por,
                registrado_en=c.registrado_en)


@router.post("/cyclotrons", status_code=201)
def registrar_ciclotron(body: CiclotronIn):
    try:
        c = _reg().registrar(**body.model_dump())
    except CiclotronInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _ciclotron_dict(c)


@router.get("/cyclotrons")
def listar_ciclotrones():
    return [_ciclotron_dict(c) for c in _reg().listar()]


@router.get("/cyclotrons/{ciclotron_id}/versions")
def versiones_ciclotron(ciclotron_id: str):
    try:
        return [_ciclotron_dict(c) for c in _reg().versiones(ciclotron_id)]
    except CiclotronInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/cyclotrons/{ciclotron_id}/irradiations", status_code=201)
def registrar_irradiacion(ciclotron_id: str, body: IrradiacionIn):
    try:
        irr = _reg().registrar_irradiacion(
            ciclotron_id, body.energia_mev, body.corriente_ua,
            body.tiempo_min, body.reaccion_id, body.blanco_id)
    except CiclotronInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    resp = dict(irradiacion_id=irr.irradiacion_id,
                ciclotron_id=irr.ciclotron_id,
                ciclotron_version=irr.ciclotron_version,
                energia_mev=irr.energia_mev, corriente_ua=irr.corriente_ua,
                tiempo_min=irr.tiempo_min, reaccion_id=irr.reaccion_id,
                blanco_id=irr.blanco_id, registrada_en=irr.registrada_en,
                potencia_haz_w=round(body.energia_mev * body.corriente_ua, 1),
                nota_honestidad=NOTA_COTA_SUPERIOR)
    # actividad EOB del motor de rendimiento real (σ(E) IAEA · S(E) ATIMA)
    try:
        r = _service.compute(
            reaction_id=irr.reaccion_id, target_id=irr.blanco_id,
            beam_energy_mev=irr.energia_mev, current_ua=irr.corriente_ua,
            irradiation_time_min=irr.tiempo_min)
        resp["eob"] = dict(
            eob_activity_gbq=round(r.eob_activity_gbq, 3),
            eob_uncertainty_gbq=round(
                r.eob_activity_gbq * r.relative_uncertainty, 3),
            saturation_yield_mbq_ua=round(r.saturation_yield_mbq_ua, 1),
            saturation_factor=round(r.saturation_factor, 5),
            dataset_id=r.dataset_id, stopping_source=r.stopping_source)
    except ValueError as exc:
        resp["eob"] = {"no_demostrable": True, "motivo": str(exc)}
    return resp


@router.get("/cyclotrons/{ciclotron_id}/irradiations")
def historial_irradiaciones(ciclotron_id: str):
    try:
        _reg().obtener(ciclotron_id)
    except CiclotronInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return [dict(irradiacion_id=i.irradiacion_id,
                 energia_mev=i.energia_mev, corriente_ua=i.corriente_ua,
                 tiempo_min=i.tiempo_min, reaccion_id=i.reaccion_id,
                 registrada_en=i.registrada_en)
            for i in _reg().irradiaciones(ciclotron_id)]


@router.get("/stopping-power/status")
def estado_stopping_power():
    """19.10: proveedor de poder de frenado REAL configurado + SRIM honesto."""
    prov = _service.stopping_status() if _service else None
    return {
        "proveedor_configurado": prov or {"estado": "no_inicializado"},
        "srim": {
            "estado": "no_configurado",
            "motivo": ("SRIM es software propietario (solo Windows, sin "
                       "licencia en esta plataforma): nunca se simula su "
                       "salida; su rol lo cubre el proveedor ATIMA/CATIMA "
                       "con fuente versionada, y la integración PSTAR/NIST "
                       "queda registrada como pendiente (19.10)"),
        },
    }
