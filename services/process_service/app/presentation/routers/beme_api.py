"""Router REST del Building Environmental Management Engine (cap. 35).

  POST /api/v1/beme/sensors                  — Sensor Manager 35.6
  POST /api/v1/beme/sensors/{id}/state
  GET  /api/v1/beme/sensors
  POST /api/v1/beme/zones                    — config versionada 35.11
  GET  /api/v1/beme/zones/{area_id}
  GET  /api/v1/beme/zones/{area_id}/status   — estado vs objetivo 35.15
  POST /api/v1/beme/hvac                     — HVAC Manager 35.7
  GET  /api/v1/beme/hvac
  POST /api/v1/beme/measurements             — medición 35.13/35.21
  GET  /api/v1/beme/measurements
  GET  /api/v1/beme/pressure/gradient        — gradiente 35.8
  GET  /api/v1/beme/pressure/stability/{area_id}
  GET  /api/v1/beme/events                   — Alarm Manager 35.12
  GET  /api/v1/beme/audit                    — auditoría 35.23

El BEME monitorea y registra; NO controla HVAC ni utilidades (35.3).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.domain.beme import (BemeEngine, BemeInvalido, CondicionesObjetivo,
                             Sensor, UnidadHvac)

router = APIRouter(prefix="/api/v1/beme", tags=["building-environmental"])

_engine: BemeEngine | None = None


def init(engine: BemeEngine | None = None) -> None:
    global _engine
    _engine = engine or BemeEngine()


def _guard(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except BemeInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/sensors", status_code=201)
def registrar_sensor(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_sensor, Sensor(**payload), usuario)


@router.post("/sensors/{sensor_id}/state")
def estado_sensor(sensor_id: str, payload: dict) -> dict:
    return _guard(_engine.cambiar_estado_sensor, sensor_id,
                  payload["estado"], payload.get("usuario", "sistema"))


@router.get("/sensors")
def sensores() -> list[dict]:
    return _engine.sensores()


@router.post("/zones", status_code=201)
def configurar_zona(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.configurar_zona, payload["area_id"],
                  payload["clasificacion"],
                  CondicionesObjetivo(**payload["objetivo"]),
                  payload["version"], usuario)


@router.get("/zones/{area_id}")
def zona(area_id: str) -> dict:
    return _guard(_engine.zona, area_id)


@router.get("/zones/{area_id}/status")
def estado_zona(area_id: str) -> dict:
    return _guard(_engine.estado_zona, area_id)


@router.post("/hvac", status_code=201)
def registrar_hvac(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_hvac, UnidadHvac(**payload), usuario)


@router.get("/hvac")
def hvac() -> list[dict]:
    return _engine.hvac()


@router.post("/measurements", status_code=201)
def medicion(payload: dict) -> dict:
    return _guard(_engine.registrar_medicion, payload["sensor_id"],
                  float(payload["valor"]), payload["calidad"],
                  payload["origen"], payload.get("timestamp"))


@router.get("/measurements")
def mediciones(area_id: str | None = Query(None)) -> list[dict]:
    return _engine.mediciones(area_id)


@router.get("/pressure/gradient")
def gradiente(area_origen: str = Query(...),
              area_destino: str = Query(...)) -> dict:
    return _engine.gradiente_presion(area_origen, area_destino)


@router.get("/pressure/stability/{area_id}")
def estabilidad(area_id: str, n: int = Query(10, ge=2)) -> dict:
    return _engine.estabilidad_presion(area_id, n)


@router.get("/events")
def eventos(area_id: str | None = Query(None)) -> list[dict]:
    return _engine.eventos(area_id)


@router.get("/audit")
def auditoria() -> list[dict]:
    return _engine.auditoria()
