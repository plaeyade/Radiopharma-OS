"""Router REST del Clinical Delivery & Dose Management Engine (cap. 32).

  POST /api/v1/clinical/schedule                    — programar paciente 32.7
  GET  /api/v1/clinical/schedule                    — programación vigente
  POST /api/v1/clinical/doses/assign                — asignar dosis 32.6/32.21
  POST /api/v1/clinical/doses/{id}/transition       — entrega/administración
  GET  /api/v1/clinical/doses/{id}                  — trazabilidad 32.19
  POST /api/v1/clinical/rescheduling/propose        — propuesta 32.11
  POST /api/v1/clinical/rescheduling/{id}/confirm   — confirmación 32.11
  GET  /api/v1/clinical/audit                       — auditoría 32.23
  GET  /api/v1/clinical/decay-status                — estado NNDC (32.8)

El Decay Calculator usa exclusivamente el NNDC Service: si no está
disponible, la asignación devuelve 503 honesto (nunca se simula λ).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.clinical_delivery import (CitaPaciente, ClinicalDeliveryEngine,
                                          ClinicoInvalido, Dosis,
                                          NndsDecayClient, NndsUnavailable)

router = APIRouter(prefix="/api/v1/clinical", tags=["clinical-delivery"])


class _State:
    def __init__(self, engine: ClinicalDeliveryEngine | None = None) -> None:
        self.engine = engine or ClinicalDeliveryEngine(NndsDecayClient())


_state: _State | None = None


def init(state: _State | None = None) -> None:
    global _state
    _state = state or _State()


class CitaIn(BaseModel):
    cita_id: str
    procedimiento: str
    horario: str
    prioridad: int = 3
    usuario: str = "sistema"


class AsignacionIn(BaseModel):
    dosis_id: str
    lote_id: str
    cita_id: str
    actividad_asignada_gbq: float
    volumen_ml: float
    destino: str
    instante_administracion: str
    lote: dict          # lote_id, nuclide, actividad_gbq,
                        # referencia_temporal, liberado_qc
    usuario: str = "sistema"


class TransicionIn(BaseModel):
    evento: str
    usuario: str = "sistema"


class PropuestaIn(BaseModel):
    cita_id: str
    retraso_min: float
    nuevo_horario: str
    usuario: str = "sistema"


class ConfirmacionIn(BaseModel):
    usuario_autorizado: str


@router.get("/decay-status")
def decay_status() -> dict:
    """Estado honesto del Decay Calculator (32.8)."""
    import os
    base = os.environ.get("NUCLEAR_DATA_URL", "")
    return {"fuente": "NNDC Service",
            "nuclear_data_url_configurada": bool(base),
            "nota": "el motor nunca usa constantes de decaimiento locales"}


@router.post("/schedule", status_code=201)
def programar(payload: CitaIn) -> dict:
    try:
        return _state.engine.programar_paciente(
            CitaPaciente(cita_id=payload.cita_id,
                         procedimiento=payload.procedimiento,
                         horario=payload.horario,
                         prioridad=payload.prioridad), payload.usuario)
    except ClinicoInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/schedule")
def programacion() -> list[dict]:
    return _state.engine.programacion()


@router.post("/doses/assign", status_code=201)
def asignar(payload: AsignacionIn) -> dict:
    try:
        return _state.engine.asignar_dosis(
            Dosis(dosis_id=payload.dosis_id, lote_id=payload.lote_id,
                  cita_id=payload.cita_id,
                  actividad_asignada_gbq=payload.actividad_asignada_gbq,
                  volumen_ml=payload.volumen_ml, destino=payload.destino),
            payload.lote, payload.instante_administracion, payload.usuario)
    except NndsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ClinicoInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/doses/{dosis_id}/transition", status_code=201)
def transicion(dosis_id: str, payload: TransicionIn) -> dict:
    try:
        return _state.engine.registrar_transicion(
            dosis_id, payload.evento, payload.usuario)
    except ClinicoInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/doses/{dosis_id}")
def trazabilidad(dosis_id: str) -> dict:
    try:
        return _state.engine.trazabilidad_dosis(dosis_id)
    except ClinicoInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/rescheduling/propose", status_code=201)
def proponer(payload: PropuestaIn) -> dict:
    try:
        return _state.engine.proponer_reprogramacion(
            payload.cita_id, payload.retraso_min, payload.nuevo_horario,
            payload.usuario)
    except ClinicoInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/rescheduling/{propuesta_id}/confirm")
def confirmar(propuesta_id: str, payload: ConfirmacionIn) -> dict:
    try:
        return _state.engine.confirmar_reprogramacion(
            propuesta_id, payload.usuario_autorizado)
    except ClinicoInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/audit")
def auditoria() -> list[dict]:
    return _state.engine.auditoria()
