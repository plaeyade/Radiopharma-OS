"""Router REST del MLOps & AI Lifecycle Management Engine (cap. 42).

  POST /api/v1/mlops/datasets              — Dataset Manager 42.6
  GET  /api/v1/mlops/datasets
  POST /api/v1/mlops/experiments           — Experiment Tracker 42.7
  GET  /api/v1/mlops/experiments
  POST /api/v1/mlops/models                — Model Registry 42.8
  POST /api/v1/mlops/models/{id}/approve   — governance 42.11/42.20
  POST /api/v1/mlops/models/{id}/deploy    — sólo aprobados 42.8
  POST /api/v1/mlops/models/{id}/revert
  POST /api/v1/mlops/models/{id}/retire
  GET  /api/v1/mlops/models
  GET  /api/v1/mlops/models/{id}/history   — gestión temporal 42.12
  POST /api/v1/mlops/models/{id}/metrics   — Monitoring Engine 42.10
  GET  /api/v1/mlops/models/{id}/metrics
  GET  /api/v1/mlops/deployments
  GET  /api/v1/mlops/audit
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.domain.mlops import (Dataset, Experimento, MlopsEngine,
                              MlopsInvalido)

router = APIRouter(prefix="/api/v1/mlops", tags=["mlops-lifecycle"])

_engine: MlopsEngine | None = None


def init(engine: MlopsEngine | None = None) -> None:
    global _engine
    _engine = engine or MlopsEngine()


def _guard(fn, *args):
    try:
        return fn(*args)
    except MlopsInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/datasets", status_code=201)
def registrar_dataset(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_dataset, Dataset(**payload), usuario)


@router.get("/datasets")
def datasets() -> list[dict]:
    return _engine.datasets()


@router.post("/experiments", status_code=201)
def registrar_experimento(payload: dict) -> dict:
    usuario = payload.pop("usuario", "sistema")
    return _guard(_engine.registrar_experimento, Experimento(**payload),
                  usuario)


@router.get("/experiments")
def experimentos(modelo_id: str | None = Query(None)) -> list[dict]:
    return _engine.experimentos(modelo_id)


@router.post("/models", status_code=201)
def registrar_modelo(payload: dict) -> dict:
    return _guard(_engine.registrar_modelo, payload["modelo_id"],
                  payload["version"], payload["experimento_id"],
                  payload.get("usuario", "sistema"))


@router.post("/models/{modelo_id}/approve")
def aprobar(modelo_id: str, payload: dict) -> dict:
    return _guard(_engine.aprobar_modelo, modelo_id,
                  payload.get("responsable", ""),
                  payload.get("documentacion", ""),
                  payload.get("usuario", "sistema"))


@router.post("/models/{modelo_id}/deploy")
def desplegar(modelo_id: str, payload: dict) -> dict:
    return _guard(_engine.desplegar, modelo_id, payload["entorno"],
                  payload.get("usuario", "sistema"))


@router.post("/models/{modelo_id}/revert")
def revertir(modelo_id: str, payload: dict) -> dict:
    return _guard(_engine.revertir, modelo_id, payload["motivo"],
                  payload.get("usuario", "sistema"))


@router.post("/models/{modelo_id}/retire")
def retirar(modelo_id: str, payload: dict) -> dict:
    return _guard(_engine.retirar, modelo_id,
                  payload.get("usuario", "sistema"))


@router.get("/models")
def modelos() -> list[dict]:
    return _engine.modelos()


@router.get("/models/{modelo_id}/history")
def historial(modelo_id: str) -> list[dict]:
    return _guard(_engine.historial_modelo, modelo_id)


@router.post("/models/{modelo_id}/metrics", status_code=201)
def metrica(modelo_id: str, payload: dict) -> dict:
    return _guard(_engine.registrar_metrica, modelo_id,
                  payload["metrica"], float(payload["valor"]),
                  payload.get("usuario", "sistema"))


@router.get("/models/{modelo_id}/metrics")
def metricas(modelo_id: str) -> list[dict]:
    return _engine.metricas(modelo_id)


@router.get("/deployments")
def despliegues() -> list[dict]:
    return _engine.despliegues()


@router.get("/audit")
def auditoria() -> list[dict]:
    return _engine.auditoria()
