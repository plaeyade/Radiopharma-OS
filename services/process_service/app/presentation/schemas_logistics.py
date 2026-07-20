"""
Esquemas Pydantic del Logistics Twin.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FacilityOut(BaseModel):
    facility_id: str
    name: str
    kind: str
    lat: float
    lon: float
    validated: bool


class RouteIn(BaseModel):
    origin_id: str = Field(..., examples=["cyclotron_main"])
    dest_id: str = Field(..., examples=["hosp_norte"])
    protocol_id: str = Field(..., examples=["fdg_18f"])
    eos_activity_gbq: float = Field(..., gt=0, examples=[66.7])
    mode: str = Field("road", examples=["road"])
    tdg_buffer_min: float = Field(90.0, ge=0)
    courier_min: float = Field(30.0, ge=0)
    drone_id: Optional[str] = Field(None, examples=["vtol_ala_fija_pesado"])
    shielding_kg: float = Field(20.0, ge=0)
    preflight_min: float = Field(20.0, ge=0)


class DroneOut(BaseModel):
    drone_id: str
    name: str
    drone_class: str
    cruise_kmh: float
    range_km: float
    max_payload_kg: float
    validated: bool
    note: str
    source: str


class LegOut(BaseModel):
    kind: str
    origin: str
    destination: str
    duration_min: float
    distance_km: float


class RouteOut(BaseModel):
    mode: str
    origin: str
    destination: str
    legs: list[LegOut]
    total_minutes: float
    total_distance_km: float
    eos_activity_gbq: float
    arrival_activity_gbq: float
    decay_factor: float
    patient_doses_on_arrival: int
    routing_source: str
    validated: bool
    notes: list[str] = []


class ReachabilityIn(BaseModel):
    origin_id: str = Field(..., examples=["cyclotron_main"])
    protocol_id: str = Field(..., examples=["fdg_18f"])
    eos_activity_gbq: float = Field(..., gt=0, examples=[66.7])
    bands_minutes: Optional[list[float]] = Field(
        None, examples=[[15, 30, 60, 90, 120]])


class ReachBandOut(BaseModel):
    minutes: float
    radius_km: float
    arrival_activity_gbq: float


class FacilityReachOut(BaseModel):
    facility_id: str
    name: str
    kind: str
    travel_minutes: float
    distance_km: float
    arrival_activity_gbq: float
    feasible_one_dose: bool


class ReachabilityOut(BaseModel):
    origin: str
    nuclide: str
    eos_activity_gbq: float
    half_life_min: float
    max_delivery_minutes_one_dose: float
    bands: list[ReachBandOut]
    facilities: list[FacilityReachOut]
    routing_source: str
    validated: bool
