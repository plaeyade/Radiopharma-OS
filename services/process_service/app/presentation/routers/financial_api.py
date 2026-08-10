"""Router REST del Financial Forecasting & Scenario Analysis Engine
(cap. 40).

  POST /api/v1/financial/scenarios              — Scenario Manager 40.6
  GET  /api/v1/financial/scenarios
  POST /api/v1/financial/scenarios/{id}/forecast — Forecast Engine 40.7
  GET  /api/v1/financial/scenarios/{id}/results  — histórico 40.19
  POST /api/v1/financial/scenarios/{id}/sensitivity — Sensitivity 40.8
  POST /api/v1/financial/scenarios/{id}/investment — Investment 40.9
  POST /api/v1/financial/scenarios/{id}/risk       — Risk Analyzer 40.10
  GET  /api/v1/financial/scenarios/{id}/kpis       — KPI Generator 40.11
  GET  /api/v1/financial/audit                     — auditoría 40.22

Los escenarios son aislados: nunca alteran registros contables ni la
operación real (40.3). Las evaluaciones de inversión son PROPUESTAS
de soporte a la decisión (41.9).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.financial_forecasting import (EscenarioFinanciero,
                                              FinancialForecastEngine,
                                              FinanzasInvalidas)

router = APIRouter(prefix="/api/v1/financial", tags=["financial-forecasting"])

_engine: FinancialForecastEngine | None = None


def init(engine: FinancialForecastEngine | None = None) -> None:
    global _engine
    _engine = engine or FinancialForecastEngine()


def _guard(fn, *args):
    try:
        return fn(*args)
    except FinanzasInvalidas as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/scenarios", status_code=201)
def registrar(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_escenario,
                  EscenarioFinanciero(**payload), usuario)


@router.get("/scenarios")
def escenarios() -> list[dict]:
    return _engine.escenarios()


@router.post("/scenarios/{escenario_id}/forecast", status_code=201)
def proyectar(escenario_id: str, payload: dict | None = None) -> dict:
    return _guard(_engine.proyectar, escenario_id,
                  (payload or {}).get("usuario", "sistema"))


@router.get("/scenarios/{escenario_id}/results")
def resultados(escenario_id: str) -> list[dict]:
    return _engine.resultados(escenario_id)


@router.post("/scenarios/{escenario_id}/sensitivity")
def sensibilidad(escenario_id: str, payload: dict) -> dict:
    return _guard(_engine.sensibilidad, escenario_id, payload["parametro"],
                  [float(v) for v in payload["variaciones_pct"]],
                  payload.get("usuario", "sistema"))


@router.post("/scenarios/{escenario_id}/investment")
def inversion(escenario_id: str, payload: dict) -> dict:
    return _guard(_engine.evaluar_inversion, escenario_id,
                  float(payload["capex"]),
                  float(payload["delta_ingresos_mensual"]),
                  float(payload["delta_coste_mensual"]),
                  float(payload.get("tasa_descuento_anual_pct", 8.0)),
                  int(payload.get("horizonte_meses", 60)),
                  payload.get("usuario", "sistema"))


@router.post("/scenarios/{escenario_id}/risk")
def riesgo(escenario_id: str, payload: dict) -> dict:
    return _guard(_engine.analizar_riesgo, escenario_id, payload["evento"],
                  payload.get("usuario", "sistema"))


@router.get("/scenarios/{escenario_id}/kpis")
def kpis(escenario_id: str) -> dict:
    return _guard(_engine.kpis, escenario_id, "sistema")


@router.get("/audit")
def auditoria() -> list[dict]:
    return _engine.auditoria()
