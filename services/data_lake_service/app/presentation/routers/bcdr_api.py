"""Router REST del Business Continuity, DR & Resilience Engine (cap. 50).

  POST /api/v1/bcdr/plans                    — planes 50.6
  POST /api/v1/bcdr/plans/{id}/approve       — validación 50.19
  GET  /api/v1/bcdr/plans
  POST /api/v1/bcdr/backup-policies          — políticas 50.8
  POST /api/v1/bcdr/backups                  — respaldo real verificado
  GET  /api/v1/bcdr/backups
  POST /api/v1/bcdr/dr-events                — eventos DR 50.7
  POST /api/v1/bcdr/dr-events/{id}/close
  GET  /api/v1/bcdr/dr-events
  POST /api/v1/bcdr/replication              — configurar 50.9
  GET  /api/v1/bcdr/replication              — estado honesto
  POST /api/v1/bcdr/ha-services              — registrar servicio 50.10
  GET  /api/v1/bcdr/ha-check                 — chequeo real /health
  GET  /api/v1/bcdr/resilience               — indicadores 50.11
  GET  /api/v1/bcdr/audit                    — auditoría 50.21
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.bcdr import (BcdrEngine, BcdrInvalido, PlanContinuidad,
                             PoliticaBackup)

router = APIRouter(prefix="/api/v1/bcdr", tags=["business-continuity"])

_engine: BcdrEngine | None = None


def init(engine: BcdrEngine | None = None) -> None:
    global _engine
    _engine = engine or BcdrEngine()


def _guard(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except BcdrInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/plans", status_code=201)
def registrar_plan(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_plan, PlanContinuidad(**payload),
                  usuario)


@router.post("/plans/{plan_id}/approve")
def aprobar(plan_id: str, payload: dict) -> dict:
    return _guard(_engine.aprobar_plan, plan_id,
                  payload.get("usuario", "sistema"))


@router.get("/plans")
def planes() -> list[dict]:
    return _engine.planes()


@router.post("/backup-policies", status_code=201)
def registrar_politica(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_politica_backup,
                  PoliticaBackup(**payload), usuario)


@router.post("/backups", status_code=201)
def ejecutar_backup(payload: dict) -> dict:
    return _guard(_engine.ejecutar_backup, payload["politica_id"],
                  payload["ruta_origen"], payload.get("usuario", "sistema"))


@router.get("/backups")
def respaldos() -> list[dict]:
    return _engine.respaldos()


@router.post("/dr-events", status_code=201)
def evento_dr(payload: dict) -> dict:
    return _guard(_engine.registrar_evento_dr, payload["evento_id"],
                  payload["tipo"], payload["descripcion"],
                  payload["inicio"], payload.get("usuario", "sistema"))


@router.post("/dr-events/{evento_id}/close")
def cerrar_evento(evento_id: str, payload: dict) -> dict:
    return _guard(_engine.cerrar_evento_dr, evento_id, payload["fin"],
                  payload.get("usuario", "sistema"))


@router.get("/dr-events")
def eventos() -> list[dict]:
    return _engine.eventos_dr()


@router.post("/replication")
def configurar_replicacion(payload: dict) -> dict:
    return _guard(_engine.configurar_replicacion, payload["estrategia"],
                  payload["destinos"], payload.get("usuario", "sistema"))


@router.get("/replication")
def estado_replicacion() -> dict:
    return _engine.estado_replicacion()


@router.post("/ha-services", status_code=201)
def registrar_servicio(payload: dict) -> dict:
    return _guard(_engine.registrar_servicio_ha, payload["nombre"],
                  payload["health_url"], payload.get("usuario", "sistema"))


@router.get("/ha-check")
def chequear() -> dict:
    return _engine.chequear_disponibilidad()


@router.get("/resilience")
def resiliencia() -> dict:
    return _engine.resiliencia()


@router.get("/audit")
def auditoria() -> list[dict]:
    return _engine.auditoria()
