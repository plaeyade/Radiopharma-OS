"""Router REST de Activación neutrónica — Bateman (Fase 28).

  POST /api/v1/activacion/calculos        — registrar cálculo (append-only)
  GET  /api/v1/activacion/calculos        — historial de cálculos
  GET  /api/v1/activacion/culpables       — catálogo con fuentes citadas
  GET  /api/v1/activacion/audit           — auditoría ALCOA+
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.activation import (ActivacionInvalida, ActivationEngine,
                                   CalculoActivacion)

router = APIRouter(prefix="/api/v1/activacion", tags=["activation"])

_engine: ActivationEngine | None = None


def init(engine: ActivationEngine | None = None) -> None:
    global _engine
    _engine = engine or ActivationEngine()


def _guard(fn, *args):
    try:
        return fn(*args)
    except ActivacionInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/calculos", status_code=201)
def calcular(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.calcular, CalculoActivacion(**payload), usuario)


@router.get("/calculos")
def calculos() -> list[dict]:
    return _engine.calculos()


@router.get("/culpables")
def culpables() -> dict:
    return _engine.culpables()


@router.get("/audit")
def auditoria() -> list[dict]:
    return _engine.auditoria()
