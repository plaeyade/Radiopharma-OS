"""
Esquemas Pydantic de la API del Yield Engine.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ProductionRequest(BaseModel):
    reaction_id: str = Field(..., examples=["o18_p_n_f18"])
    target_id: str = Field(..., examples=["h2_18o"])
    beam_energy_mev: float = Field(..., gt=0, le=40, examples=[16.5])
    current_ua: float = Field(..., gt=0, le=300, examples=[37.0])
    irradiation_time_min: float = Field(..., gt=0, le=600, examples=[60.0])
    enrichment: Optional[float] = Field(None, gt=0, le=1.0)


class ProductionResponse(BaseModel):
    reaction_id: str
    product_nuclide: str
    beam_energy_mev: float
    exit_energy_mev: float
    current_ua: float
    irradiation_time_min: float
    saturation_yield_mbq_ua: float
    saturation_yield_gbq_ua: float
    eob_activity_gbq: float
    eob_activity_gbq_uncertainty: float
    yield_gbq_ua: float
    saturation_factor: float
    relative_uncertainty: float
    dataset_id: str
    stopping_source: str


class BurnupRequest(BaseModel):
    reaction_id: str = Field(..., examples=["o18_p_n_f18"])
    target_id: str = Field(..., examples=["h2_18o"])
    beam_energy_mev: float = Field(..., gt=0, le=40)
    current_ua: float = Field(..., gt=0, le=300)
    irradiation_time_min: float = Field(..., gt=0, le=600)
    beam_spot_cm2: float = Field(1.0, gt=0, description="Área efectiva del haz sobre el blanco")
    burnup_xs_mb: float = Field(500.0, gt=0, description="Sección eficaz efectiva de quemado")


class BurnupResponse(BaseModel):
    reaction_id: str
    product_nuclide: str
    beam_energy_mev: float
    current_ua: float
    irradiation_time_min: float
    beam_spot_cm2: float
    burnup_xs_mb: float
    burnup_rate_s: float = Field(..., alias="burnup_rate_s-1")
    target_depletion_fraction: float
    eob_no_burnup_gbq: float
    eob_with_burnup_gbq: float
    loss_gbq: float
    loss_percent: float
    model: str

    model_config = {"populate_by_name": True}


class BurnupMultizoneRequest(BaseModel):
    reaction_id: str = Field(..., examples=["o18_p_n_f18"])
    target_id: str = Field(..., examples=["h2_18o"])
    beam_energy_mev: float = Field(..., gt=0, le=40)
    current_ua: float = Field(..., gt=0, le=300)
    irradiation_time_min: float = Field(..., gt=0, le=600)
    beam_spot_cm2: float = Field(1.0, gt=0,
                                 description="Área efectiva del haz sobre el blanco")
    n_zones: int = Field(10, ge=1, le=50,
                         description="Número de capas axiales (1 = grupo único)")
    burnup_xs_max_mb: float = Field(
        800.0, gt=0,
        description="Meseta de la sección de reacción no elástica (modelo con umbral)")


class BurnupZoneOut(BaseModel):
    index: int
    e_in_mev: float
    e_out_mev: float
    production_weight: float
    burnup_xs_mb: float
    flux_attenuation: float
    burnup_rate_s: float
    depletion_fraction: float


class BurnupMultizoneResponse(BaseModel):
    reaction_id: str
    product_nuclide: str
    beam_energy_mev: float
    current_ua: float
    irradiation_time_min: float
    beam_spot_cm2: float
    burnup_xs_max_mb: float
    n_zones: int
    zones: list[BurnupZoneOut]
    burnup_rate_max_s: float
    depletion_weighted: float
    depletion_max: float
    eob_no_burnup_gbq: float
    eob_with_burnup_gbq: float
    loss_gbq: float
    model: str
