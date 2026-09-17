"""Router REST de Salud de Componentes Consumibles (Fase 27, cap. 34 ext.).

  POST /api/v1/componentes                      — registrar pieza sacrificial
  GET  /api/v1/componentes                      — tablero completo de desgaste
  GET  /api/v1/componentes/{id}/salud           — salud de un componente
  POST /api/v1/componentes/{id}/uso             — consumo REAL con origen
  POST /api/v1/componentes/{id}/reemplazo       — decisión operativa 18.10
  GET  /api/v1/componentes/audit                — auditoría ALCOA+
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.component_health import (ComponentHealth,
                                         ComponentHealthInvalido, Componente,
                                         EventoUso, Reemplazo)
from app.domain.facility_twin import FacilityTwin

router = APIRouter(prefix="/api/v1/componentes", tags=["component-health"])

_salud: ComponentHealth | None = None


def init(twin: FacilityTwin | None = None,
         salud: ComponentHealth | None = None) -> None:
    global _salud
    _salud = salud or ComponentHealth(twin or FacilityTwin())


def _guard(fn, *args):
    try:
        return fn(*args)
    except ComponentHealthInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("", status_code=201)
def registrar_componente(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_salud.registrar_componente, Componente(**payload), usuario)


@router.get("")
def tablero() -> list[dict]:
    return _salud.tablero()


@router.get("/audit")
def auditoria() -> list[dict]:
    return _salud.auditoria()


@router.get("/{componente_id}/salud")
def salud(componente_id: str) -> dict:
    return _guard(_salud.salud, componente_id)


@router.post("/{componente_id}/uso", status_code=201)
def registrar_uso(componente_id: str, payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_salud.registrar_uso, componente_id,
                  EventoUso(**payload), usuario)


@router.post("/{componente_id}/reemplazo", status_code=201)
def registrar_reemplazo(componente_id: str, payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_salud.registrar_reemplazo, componente_id,
                  Reemplazo(**payload), usuario)
