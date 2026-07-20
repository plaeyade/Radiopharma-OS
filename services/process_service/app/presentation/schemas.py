"""
Esquemas Pydantic del Process Twin.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

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


class ScheduleIn(BaseModel):
    protocol_id: str = Field(..., examples=["fdg_18f"])
    dose_time: datetime = Field(..., examples=["2026-07-20T14:00:00Z"])
    irradiation_time_min: float = Field(..., gt=0, examples=[60.0])
    setup_min: float = Field(0.0, ge=0, examples=[10.0])
    eos_target_gbq: Optional[float] = Field(None, gt=0, examples=[30.0])
    target_doses: Optional[int] = Field(None, gt=0, examples=[80])


class ScheduledStepOut(BaseModel):
    name: str
    start: datetime
    end: datetime
    activity_out_gbq: float


class ScheduleOut(BaseModel):
    protocol_id: str
    nuclide: str
    eos_target_gbq: float
    eob_required_gbq: float
    dose_time: datetime
    beam_start: datetime
    setup_min: float
    irradiation_time_min: float
    eob_time: datetime
    total_lead_time_min: float
    patient_doses: int
    validated: bool
    steps: list[ScheduledStepOut]


class BottleneckIn(BaseModel):
    protocol_id: str = Field(..., examples=["fdg_18f"])
    eob_activity_gbq: float = Field(..., gt=0, examples=[108.9])


class StepBottleneckOut(BaseModel):
    name: str
    loss_gbq: float
    decay_loss_gbq: float
    efficiency_loss_gbq: float
    eos_gain_1min_faster_gbq: float
    eos_gain_1pp_efficiency_gbq: float


class BottleneckOut(BaseModel):
    protocol_id: str
    nuclide: str
    eob_activity_gbq: float
    eos_activity_gbq: float
    total_loss_gbq: float
    dominant_loss_step: str
    steps: list[StepBottleneckOut]

class AppointmentIn(BaseModel):
    time: datetime = Field(..., examples=["2026-07-20T14:00:00Z"])
    dose_gbq: Optional[float] = Field(None, gt=0, examples=[0.37])
    label: str = ""


class DoseCalendarIn(BaseModel):
    protocol_id: str = Field(..., examples=["fdg_18f"])
    eos_activity_gbq: float = Field(..., gt=0, examples=[66.7])
    eos_time: datetime = Field(..., examples=["2026-07-20T12:30:00Z"])
    appointments: list[AppointmentIn] = Field(..., min_length=1)


class DoseSlotOut(BaseModel):
    label: str
    time: datetime
    dose_gbq: float
    inventory_before_gbq: float
    feasible: bool
    inventory_after_gbq: float


class DoseCalendarOut(BaseModel):
    protocol_id: str
    nuclide: str
    half_life_min: float
    eos_activity_gbq: float
    eos_time: datetime
    required_eos_gbq: float
    patients_served: int
    patients_total: int
    total_drawn_gbq: float
    remaining_after_last_gbq: float
    validated: bool
    slots: list[DoseSlotOut]


# ---------------- Plan de campaña (Process Twin F4) -------------------------

class CampaignIn(BaseModel):
    protocol_id: str = Field(..., examples=["fdg_18f"])
    capacity_gbq: float = Field(..., gt=0, examples=[40.0],
                                description="Capacidad EOS por lote")
    prep_min: float = Field(30.0, ge=0,
                            description="Margen EOS → primera cita del lote")
    turnaround_min: float = Field(240.0, ge=0,
                                  description="Separación mínima entre lotes")
    appointments: list[AppointmentIn] = Field(..., min_length=1)


class CampaignBatchOut(BaseModel):
    index: int
    eos_time: datetime
    required_eos_gbq: float
    capacity_gbq: float
    headroom_gbq: float
    utilization: float
    n_appointments: int
    first_appointment: datetime
    last_appointment: datetime
    total_dose_gbq: float


class CampaignOut(BaseModel):
    protocol_id: str
    half_life_min: float
    capacity_gbq: float
    prep_min: float
    turnaround_min: float
    batches: list[CampaignBatchOut]
    n_appointments: int
    n_served: int
    unserved: list[AppointmentIn]
    total_required_eos_gbq: float
    total_dose_gbq: float
