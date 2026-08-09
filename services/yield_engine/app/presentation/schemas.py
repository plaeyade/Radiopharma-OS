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


# ------------- Burnup radial 2D + Thermal Engine + Elmer FEM --------------

class BurnupRadialRequest(BaseModel):
    reaction_id: str = Field(..., examples=["o18_p_n_f18"])
    target_id: str = Field(..., examples=["h2_18o"])
    beam_energy_mev: float = Field(..., gt=0, le=40)
    current_ua: float = Field(..., gt=0, le=300)
    irradiation_time_min: float = Field(..., gt=0, le=600)
    beam_spot_cm2: float = Field(1.0, gt=0,
                                 description="Área efectiva del haz sobre el blanco")
    beam_sigma_cm: float = Field(
        0.15, gt=0, description="σ radial del perfil gaussiano del haz")
    n_rings: int = Field(20, ge=1, le=200,
                         description="Anillos concéntricos del modelo radial")
    burnup_xs_max_mb: float = Field(
        800.0, gt=0,
        description="Meseta de la sección no elástica (referencia 1D)")


class RadialRingOut(BaseModel):
    index: int
    r_in_cm: float
    r_out_cm: float
    r_mean_cm: float
    flux_rel: float
    production_weight: float
    burnup_rate_s: float
    depletion_fraction: float


class BurnupRadialResponse(BaseModel):
    reaction_id: str
    product_nuclide: str
    beam_energy_mev: float
    current_ua: float
    irradiation_time_min: float
    beam_spot_cm2: float
    beam_sigma_cm: float
    spot_radius_cm: float
    n_rings: int
    burnup_xs_max_mb: float
    burnup_xs_eff_mb: float
    flux_peak_cm2_s: float
    flux_mean_cm2_s: float
    peak_factor: float
    rings: list[RadialRingOut]
    burnup_rate_max_s: float
    depletion_weighted: float
    depletion_max: float
    eob_ideal_gbq: float
    eob_1d_gbq: float
    eob_2d_gbq: float
    loss_vs_ideal_gbq: float
    loss_vs_1d_gbq: float
    model: str


class ThermalTargetRequest(BaseModel):
    beam_energy_mev: float = Field(..., gt=0, le=40)
    current_ua: float = Field(..., gt=0, le=300)
    beam_spot_cm2: float = Field(1.0, gt=0)
    target_thickness_cm: float = Field(0.5, gt=0,
                                       description="Espesor del blanco en la dirección del haz")
    conductivity_w_cm_k: float = Field(
        0.006, gt=0, description="Conductividad del medio blanco (agua: 0.006 W/cm·K)")
    film_coeff_w_cm2_k: float = Field(
        0.5, gt=0, description="Coeficiente de película del refrigerante")
    coolant_temp_k: float = Field(293.15, gt=0)
    t_limit_k: float = Field(373.15, gt=0,
                             description="Límite térmico (p.ej. ebullición del medio)")
    beam_sigma_cm: Optional[float] = Field(
        None, gt=0, description="σ del haz gaussiano (None = perfil uniforme)")


class ThermalTargetResponse(BaseModel):
    beam_power_w: float
    spot_area_cm2: float
    heat_flux_mean_w_cm2: float
    heat_flux_peak_w_cm2: float
    peak_factor: float
    delta_t_conduction_k: float
    delta_t_film_k: float
    t_peak_k: float
    t_mean_k: float
    t_limit_k: float
    margin_k: float
    within_limit: bool
    max_current_ua: float
    model: str


class ElmerCompareRequest(BaseModel):
    reaction_id: str = Field(..., examples=["o18_p_n_f18"],
                             description="Puerta canónica cap. 8.11: Yield+Burnup primero")
    target_id: str = Field(..., examples=["h2_18o"])
    irradiation_time_min: float = Field(..., gt=0, le=600,
                                        description="Para la etapa Burnup previa")
    beam_energy_mev: float = Field(..., gt=0, le=40)
    current_ua: float = Field(..., gt=0, le=300)
    beam_spot_cm2: float = Field(1.0, gt=0)
    target_thickness_cm: float = Field(0.5, gt=0)
    conductivity_w_cm_k: float = Field(0.006, gt=0)
    film_coeff_w_cm2_k: float = Field(0.5, gt=0)
    coolant_temp_k: float = Field(293.15, gt=0)
    beam_sigma_cm: Optional[float] = Field(None, gt=0)


class ElmerCompareResponse(BaseModel):
    pipeline: str
    reaction_id: str
    target_id: str
    irradiation_time_min: float
    yield_eob_gbq: float
    burnup_eob_gbq: float
    burnup_loss_gbq: float
    t_peak_fem_k: float
    t_mean_fem_k: float
    t_peak_reduced_k: float
    t_mean_reduced_k: float
    peak_rel_diff: float
    fem_conservative_bound_ok: bool
    solver: str
    model: str


# ---------------- Calibration Layer (EDS v2.0, Vol. II) --------------------

class EquipmentOut(BaseModel):
    id: str
    fabricante: str
    modelo: str
    energia_max_mev: Optional[float] = None
    energia_fija_mev: bool
    corriente_max_ua: Optional[float] = None
    reacciones_tipicas: list[str]
    notas: str


class CalibrationMeasurementIn(BaseModel):
    fecha: str = Field(..., examples=["2026-07-15"])
    eob_predicho_gbq: float = Field(..., gt=0)
    eob_medido_gbq: float = Field(..., gt=0)
    incertidumbre_gbq: float = Field(0.0, ge=0)


class CalibrationFitIn(BaseModel):
    reaction_id: str
    equipment_id: str
    medidas: list[CalibrationMeasurementIn] = Field(..., min_length=2)


class CalibrationModelOut(BaseModel):
    model_id: str
    reaction_id: str
    equipment_id: str
    version: int
    factor: float
    factor_uncertainty: float
    n_points: int
    chi2_ndf: float
    status: str
    fitted_at: str
    medidas: list[dict]


class CalibrationIndicatorsIn(BaseModel):
    """17.26/17.10: histórico de pares (teórico, medido) para evaluar
    el desempeño y la deriva del modelo físico."""
    medidas: list[CalibrationMeasurementIn] = Field(..., min_length=2)


class CalibrationIndicatorsOut(BaseModel):
    n: int
    error_abs_mean_gbq: float
    error_rel_mean: float
    error_rel_max: float
    error_rel_std: float
    trend_slope_rel_per_day: float
    trend_r2: float
    span_days: float
    drift_detected: bool
    accumulated_rel_change: float
    residual_std: float
    drift_threshold: float
    drift_note: str


class CalibratedProductionRequest(ProductionRequest):
    equipment_id: str = Field(..., examples=["iba_kiube"])


class ProductionResponseCalibrated(ProductionResponse):
    calibration: dict


# -- F3: K-factor por lote (17.6/17.21/17.22/17.25) --------------------------
class BatchMeasurementIn(BaseModel):
    """17.6: medida EOB real asociada a un lote de producción."""
    reaction_id: str
    equipment_id: str
    batch_id: str = Field(..., min_length=1)
    fecha: str = Field(..., examples=["2026-08-08"])
    eob_predicho_gbq: float = Field(..., gt=0)
    eob_medido_gbq: float = Field(..., gt=0)
    incertidumbre_gbq: float = Field(0.0, ge=0)
    operador: str = Field(..., min_length=1)
    motivo: str = Field("", description="motivo del registro (auditoría 17.25)")


class BatchMeasurementOut(BaseModel):
    reaction_id: str
    equipment_id: str
    batch_id: str
    fecha: str
    eob_predicho_gbq: float
    eob_medido_gbq: float
    incertidumbre_gbq: float
    operador: str
    k: float | None
    accepted: bool
    reasons: list[str]


class FitFromBatchesIn(BaseModel):
    reaction_id: str
    equipment_id: str
    operador: str = Field(..., min_length=1)
    motivo: str = Field(..., min_length=1,
                        description="obligatorio (17.22/17.25)")


class AuditEntryOut(BaseModel):
    fecha: str
    usuario: str
    accion: str
    aceptada: bool
    motivo: str
    evidencia: dict
    razones_rechazo: list[str]
