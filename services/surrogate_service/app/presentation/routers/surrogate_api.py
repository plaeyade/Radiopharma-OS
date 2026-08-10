"""
Router REST del Surrogate Modeling Server (EDS Vol. II, cap. 20).

  POST /api/v1/surrogates/train          — entrenamiento + puerta 20.21
  POST /api/v1/surrogates/infer          — Inference API 20.11 (+ auditoría 20.24)
  POST /api/v1/surrogates/drift/observe  — observación operativa 20.20
  GET  /api/v1/surrogates/drift/status   — estado del Drift Monitor 20.20
  GET  /api/v1/surrogates/models         — Model Registry 20.9
  GET  /api/v1/surrogates/datasets       — datasets versionados 20.6
  GET  /api/v1/surrogates/audit          — trazabilidad de inferencias 20.24
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.application.surrogate_service import (SurrogateNoEncontrado,
                                               SurrogateService)
from app.presentation.schemas import DriftObserveIn, InferIn, TrainIn

router = APIRouter(prefix="/api/v1/surrogates", tags=["surrogate-server"])

_service: SurrogateService | None = None


def init(service: SurrogateService) -> None:
    global _service
    _service = service


@router.get("/models")
def list_models() -> list[dict]:
    return _service.list_models()


@router.get("/datasets")
def list_datasets() -> list[dict]:
    return _service.list_datasets()


@router.get("/audit")
def audit_log() -> list[dict]:
    return _service.audit_log()


@router.post("/train")
def train(payload: TrainIn) -> dict:
    try:
        return _service.train_yield_surrogate(
            payload.version, payload.responsable,
            payload.umbral_rel_rmse, payload.umbral_max_rel_err)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/infer")
def infer(payload: InferIn) -> dict:
    try:
        return _service.infer(payload.model_id, payload.version,
                              payload.beam_energy_mev, payload.usuario,
                              payload.request_id)
    except SurrogateNoEncontrado as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/drift/observe")
def drift_observe(payload: DriftObserveIn) -> dict:
    try:
        return _service.drift_observe(payload.model_id, payload.version,
                                      payload.prediccion, payload.medicion,
                                      payload.fuente)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/drift/status")
def drift_status(model_id: str | None = None) -> dict:
    return _service.drift_status(model_id)
