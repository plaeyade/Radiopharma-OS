"""
Esquemas Pydantic del Process Twin.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProtocolStepOut(BaseModel):
    name: str
    duration_min: float
    efficiency: float


class ProtocolSummaryOut(BaseModel):
    protocol_id: str
    name: str
    nuclide: str
    half_life_min: float
    dose_per_patient_gbq: float
    n_steps: int
    total_time_min: float
    validated: bool


class ProtocolOut(ProtocolSummaryOut):
    source: str
    steps: list[ProtocolStepOut]


class SimulateIn(BaseModel):
    protocol_id: str = Field(..., examples=["fdg_18f"])
    eob_activity_gbq: float = Field(..., gt=0, examples=[108.9])


class StepResultOut(BaseModel):
    name: str
    duration_min: float
    efficiency: float
    activity_in_gbq: float
    activity_after_decay_gbq: float
    activity_out_gbq: float


class SimulateOut(BaseModel):
    protocol_id: str
    nuclide: str
    half_life_min: float
    eob_activity_gbq: float
    eos_activity_gbq: float
    total_time_min: float
    overall_decay_factor: float
    overall_efficiency: float
    dose_per_patient_gbq: float
    patient_doses: int
    validated: bool
    steps: list[StepResultOut]
