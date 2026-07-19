"""
Esquemas Pydantic del QC Engine.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class DecayCorrectionIn(BaseModel):
    nuclide: str = Field(..., examples=["18F"])
    activity: float = Field(..., gt=0, examples=[108.9])
    delta_time_min: float = Field(..., gt=0, examples=[45.0])
    to_future: bool = True
    relative_uncertainty: float = Field(0.02, gt=0, le=0.5)


class DecayCorrectionOut(BaseModel):
    nuclide: str
    input_activity: float
    delta_time_min: float
    direction: str
    corrected_activity: float
    relative_uncertainty: float
    half_life_min_used: float


class MeasurementIn(BaseModel):
    time_min: float = Field(..., ge=0)
    activity: float = Field(..., gt=0)
    uncertainty: Optional[float] = Field(None, gt=0)


class HalfLifeFitIn(BaseModel):
    nuclide: str = Field(..., examples=["18F"])
    measurements: list[MeasurementIn] = Field(..., min_length=3)
    tolerance_percent: float = Field(5.0, gt=0, le=50)
    chi2_threshold: float = Field(3.0, gt=0)


class HalfLifeFitOut(BaseModel):
    half_life_min: float
    half_life_uncertainty_min: float
    activity_at_t0: float
    chi_squared_reduced: float
    n_points: int
    reference_half_life_min: float
    deviation_percent: float
    within_tolerance: bool
    tolerance_percent: float
    impurity_suspected: bool


class QcEvaluateIn(BaseModel):
    product: str = Field(..., examples=["fdg"])
    nuclide: str = Field(..., examples=["18F"])
    measurements: dict[str, Optional[float]] = Field(
        ..., examples=[{"ph": 6.8, "radiochemical_purity": 0.985,
                        "radionuclidic_purity": 0.9999}])
    half_life_series: Optional[list[MeasurementIn]] = None
    tolerance_percent: float = Field(5.0, gt=0, le=50)


class RuleEvalOut(BaseModel):
    parameter: str
    measured: Optional[float]
    status: str
    detail: str
    limits: str
    source: str


class QcReportOut(BaseModel):
    product: str
    nuclide: str
    overall_status: str
    rule_evaluations: list[RuleEvalOut]
    half_life_fit: Optional[HalfLifeFitOut] = None
