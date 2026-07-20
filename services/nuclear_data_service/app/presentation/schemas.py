"""
Esquemas Pydantic de la API pública del Nuclear Data Service.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class CrossSectionPointOut(BaseModel):
    energy_mev: float
    sigma_mb: float
    dsigma_mb: Optional[float] = None


class ReactionOut(BaseModel):
    reaction_id: str
    notation: str
    projectile: str
    target_nuclide: str
    product_nuclide: str
    q_value_mev: float
    threshold_mev: float
    dataset_id: str
    n_points: int
    points: list[CrossSectionPointOut]


class DecayModeOut(BaseModel):
    mode: str
    branching_ratio: float
    endpoint_energy_kev: Optional[float] = None


class EmissionOut(BaseModel):
    type: str
    energy_kev: float
    intensity_percent: float


class DecayOut(BaseModel):
    nuclide: str
    z: int
    a: int
    half_life_s: float
    decay_constant_s: float
    decay_modes: list[DecayModeOut]
    emissions: list[EmissionOut]
    dataset_id: str


class DatasetOut(BaseModel):
    id: str
    type: str
    source: str
    retrieved: str
    sha256: Optional[str] = None
    license: str


class TalysStatusOut(BaseModel):
    available: bool
    cmd: Optional[str] = None
    version: Optional[str] = None
    reactions_cached: list[str]


class SourceSummaryOut(BaseModel):
    dataset_id: str
    n_points: int
    e_min_mev: float
    e_max_mev: float
    peak_energy_mev: float
    peak_sigma_mb: float


class CompareOut(BaseModel):
    reaction_id: str
    iaea: SourceSummaryOut
    talys: SourceSummaryOut
    n_compared: int
    max_rel_deviation: float
    rms_rel_deviation: float
