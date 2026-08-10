"""Router REST del Facility Twin (cap. 33) y Asset Lifecycle (cap. 34).

  POST /api/v1/facility/assets                      — Asset Registry 33.6
  GET  /api/v1/facility/assets
  POST /api/v1/facility/areas                       — áreas 33.8 / zonas 33.12
  GET  /api/v1/facility/areas
  POST /api/v1/facility/utilities                   — Utility Manager 33.10
  POST /api/v1/facility/utilities/{id}/state
  GET  /api/v1/facility/utilities
  POST /api/v1/facility/environment                 — medición real 33.11
  GET  /api/v1/facility/environment
  POST /api/v1/facility/assets/{id}/lifecycle       — ciclo de vida 34.7
  GET  /api/v1/facility/assets/{id}/lifecycle
  POST /api/v1/facility/maintenance/plans           — planes 34.9
  POST /api/v1/facility/maintenance                 — intervención 34.8
  POST /api/v1/facility/maintenance/{id}/close
  POST /api/v1/facility/calibrations                — Calibration 34.10
  GET  /api/v1/facility/assets/{id}/calibrations
  GET  /api/v1/facility/assets/{id}/calibration-current
  POST /api/v1/facility/certifications              — Certification 34.11
  GET  /api/v1/facility/assets/{id}/certifications
  GET  /api/v1/facility/assets/{id}/reliability     — Reliability 34.12
  POST /api/v1/facility/spares                      — Spare Parts 34.13
  POST /api/v1/facility/spares/{id}/consume
  GET  /api/v1/facility/spares
  GET  /api/v1/facility/audit                       — auditoría 33.24/34.24
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.domain.facility_twin import (Activo, Area, Calibracion,
                                      Certificacion, FacilityInvalido,
                                      FacilityTwin, Mantenimiento,
                                      MedicionAmbiental, Repuesto, Utilidad)

router = APIRouter(prefix="/api/v1/facility", tags=["facility-twin"])

_twin: FacilityTwin | None = None


def init(twin: FacilityTwin | None = None) -> None:
    global _twin
    _twin = twin or FacilityTwin()


def _guard(fn, *args):
    try:
        return fn(*args)
    except FacilityInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/assets", status_code=201)
def registrar_activo(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_twin.registrar_activo, Activo(**payload), usuario)


@router.get("/assets")
def listar_activos() -> list[dict]:
    return _twin.activos()


@router.post("/areas", status_code=201)
def registrar_area(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_twin.registrar_area, Area(**payload), usuario)


@router.get("/areas")
def listar_areas() -> list[dict]:
    return _twin.areas()


@router.post("/utilities", status_code=201)
def registrar_utilidad(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_twin.registrar_utilidad, Utilidad(**payload), usuario)


@router.post("/utilities/{utilidad_id}/state")
def estado_utilidad(utilidad_id: str, payload: dict) -> dict:
    return _guard(_twin.cambiar_estado_utilidad, utilidad_id,
                  payload["estado"], payload.get("usuario", "sistema"))


@router.get("/utilities")
def listar_utilidades() -> list[dict]:
    return _twin.utilidades()


@router.post("/environment", status_code=201)
def medicion_ambiental(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_twin.registrar_medicion_ambiental,
                  MedicionAmbiental(**payload), usuario)


@router.get("/environment")
def mediciones(area_id: str | None = Query(None)) -> list[dict]:
    return _twin.mediciones(area_id)


@router.post("/assets/{activo_id}/lifecycle", status_code=201)
def transicion_ciclo(activo_id: str, payload: dict) -> dict:
    return _guard(_twin.transicionar_ciclo, activo_id, payload["estado"],
                  payload.get("usuario", "sistema"))


@router.get("/assets/{activo_id}/lifecycle")
def historial_ciclo(activo_id: str) -> list[dict]:
    return _twin.historial_ciclo(activo_id)


@router.post("/maintenance/plans", status_code=201)
def registrar_plan(payload: dict) -> dict:
    plan_id = payload.pop("plan_id")
    usuario = payload.pop("usuario", "sistema")
    return _guard(_twin.registrar_plan, plan_id, payload, usuario)


@router.post("/maintenance", status_code=201)
def registrar_mantenimiento(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_twin.registrar_mantenimiento, Mantenimiento(**payload),
                  usuario)


@router.post("/maintenance/{intervencion_id}/close")
def cerrar_mantenimiento(intervencion_id: str, payload: dict) -> dict:
    return _guard(_twin.cerrar_mantenimiento, intervencion_id,
                  payload["fin"], payload.get("usuario", "sistema"))


@router.post("/calibrations", status_code=201)
def registrar_calibracion(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_twin.registrar_calibracion, Calibracion(**payload),
                  usuario)


@router.get("/assets/{activo_id}/calibrations")
def calibraciones(activo_id: str) -> list[dict]:
    return _twin.calibraciones(activo_id)


@router.get("/assets/{activo_id}/calibration-current")
def calibracion_vigente(activo_id: str,
                        fecha: str = Query(...)) -> dict:
    return _guard(_twin.calibracion_vigente, activo_id, fecha)


@router.post("/certifications", status_code=201)
def registrar_certificacion(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_twin.registrar_certificacion, Certificacion(**payload),
                  usuario)


@router.get("/assets/{activo_id}/certifications")
def certificaciones(activo_id: str) -> list[dict]:
    return _twin.certificaciones(activo_id)


@router.get("/assets/{activo_id}/reliability")
def confiabilidad(activo_id: str,
                  horas_periodo: float = Query(..., gt=0)) -> dict:
    return _guard(_twin.confiabilidad, activo_id, horas_periodo)


@router.post("/spares", status_code=201)
def registrar_repuesto(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_twin.registrar_repuesto, Repuesto(**payload), usuario)


@router.post("/spares/{repuesto_id}/consume")
def consumir_repuesto(repuesto_id: str, payload: dict) -> dict:
    return _guard(_twin.consumir_repuesto, repuesto_id,
                  int(payload["cantidad"]),
                  payload.get("usuario", "sistema"))


@router.get("/spares")
def repuestos() -> list[dict]:
    return _twin.repuestos()


@router.get("/audit")
def auditoria() -> list[dict]:
    return _twin.auditoria()
