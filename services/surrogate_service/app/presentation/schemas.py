"""
Schemas REST del Surrogate Modeling Server (cap. 20).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TrainIn(BaseModel):
    version: str = Field(..., min_length=1,
                         description="versión nueva del modelo (20.9)")
    responsable: str = Field(..., min_length=1)
    umbral_rel_rmse: float = Field(0.05, gt=0, le=0.5)
    umbral_max_rel_err: float = Field(0.15, gt=0, le=1.0)


class InferIn(BaseModel):
    model_id: str = "yield_sat_f18"
    version: str | None = None
    beam_energy_mev: float = Field(..., gt=0, le=250)
    usuario: str = Field(..., min_length=1)
    request_id: str | None = None


class DriftObserveIn(BaseModel):
    model_id: str = "yield_sat_f18"
    version: str | None = None
    prediccion: float = Field(..., ge=0)
    medicion: float = Field(..., gt=0)
    fuente: str = Field(..., min_length=1,
                        description="origen validado de la medición (20.20)")
