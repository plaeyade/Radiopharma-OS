"""Router REST del Sistema de Vacío (Fase 28, cap. 34 ext.).

  POST /api/v1/vacio/bombas                  — registrar bomba
  POST /api/v1/vacio/tramos                  — registrar tramo/manguera
  POST /api/v1/vacio/{id}/mediciones         — medición REAL con origen
  GET  /api/v1/vacio/bombas/{id}/salud       — salud de bomba
  GET  /api/v1/vacio/tramos/{id}/salud       — salud de tramo
  GET  /api/v1/vacio/tablero                 — tablero completo
  GET  /api/v1/vacio/audit                   — auditoría ALCOA+
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.facility_twin import FacilityTwin
from app.domain.vacuum_system import (BombaVacio, MedicionVacio, TramoLinea,
                                      VacioInvalido, VacuumSystem)

router = APIRouter(prefix="/api/v1/vacio", tags=["vacuum-system"])

_vacio: VacuumSystem | None = None


def init(twin: FacilityTwin | None = None,
         vacio: VacuumSystem | None = None) -> None:
    global _vacio
    _vacio = vacio or VacuumSystem(twin or FacilityTwin())


def _guard(fn, *args):
    try:
        return fn(*args)
    except VacioInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/bombas", status_code=201)
def registrar_bomba(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_vacio.registrar_bomba, BombaVacio(**payload), usuario)


@router.post("/tramos", status_code=201)
def registrar_tramo(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_vacio.registrar_tramo, TramoLinea(**payload), usuario)


@router.post("/{elemento_id}/mediciones", status_code=201)
def registrar_medicion(elemento_id: str, payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_vacio.registrar_medicion, elemento_id,
                  MedicionVacio(**payload), usuario)


@router.get("/bombas/{bomba_id}/salud")
def salud_bomba(bomba_id: str) -> dict:
    return _guard(_vacio.salud_bomba, bomba_id)


@router.get("/tramos/{tramo_id}/salud")
def salud_tramo(tramo_id: str) -> dict:
    return _guard(_vacio.salud_tramo, tramo_id)


@router.get("/tablero")
def tablero() -> dict:
    return _vacio.tablero()


@router.get("/audit")
def auditoria() -> list[dict]:
    return _vacio.auditoria()
