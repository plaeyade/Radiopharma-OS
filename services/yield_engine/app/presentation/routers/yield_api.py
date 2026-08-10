"""
Router REST del Yield Engine.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.application.production_service import ProductionService, REACTIONS
from app.application.target_catalog import TARGET_CATALOG
from app.infrastructure.elmer.elmer_runner import (ElmerError,
                                                   ElmerUnavailable)
from app.infrastructure.gate.gate_runner import GateError, GateUnavailable
from app.presentation.schemas import (BurnupMultizoneRequest,
                                      BurnupMultizoneResponse,
                                      BurnupRadialRequest,
                                      BurnupRadialResponse, BurnupRequest,
                                      BurnupResponse, ElmerCompareRequest,
                                      ElmerCompareResponse,
                                      ElmerThermomechanicalRequest,
                                      ElmerThermomechanicalResponse,
                                      MonteCarloRequest, MonteCarloResponse,
                                      ProductionRequest,
                                      ProductionResponse,
                                      ThermalTargetRequest,
                                      ThermalTargetResponse)

router = APIRouter(prefix="/api/v1", tags=["yield-engine"])

_service: ProductionService | None = None


def init(service: ProductionService) -> None:
    global _service
    _service = service


@router.post("/production", response_model=ProductionResponse)
def compute_production(req: ProductionRequest) -> ProductionResponse:
    try:
        r = _service.compute(
            reaction_id=req.reaction_id, target_id=req.target_id,
            beam_energy_mev=req.beam_energy_mev, current_ua=req.current_ua,
            irradiation_time_min=req.irradiation_time_min, enrichment=req.enrichment)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ProductionResponse(**production_response_dict(r))


@router.post("/production/optimize")
def optimize_production(req: dict) -> dict:
    """Optimización física de producción (Informe 18.10; cap. 41.9/41.13).

    Recomendación calculada sobre el modelo físico determinista —
    los surrogates nunca reemplazan al modelo de referencia (20.3)."""
    from app.domain.optimizer import OptimizationConstraint
    try:
        constraints = OptimizationConstraint(**{
            k: v for k, v in (req.get("restricciones") or {}).items()
            if k in OptimizationConstraint.__dataclass_fields__})
        return _service.optimize_production(
            reaction_id=req["reaction_id"], target_id=req["target_id"],
            constraints=constraints)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def production_response_dict(r) -> dict:
    """Mapeo único ProductionResult → dict de respuesta (compartido con el
    endpoint calibrado del Calibration Layer)."""
    return dict(
        reaction_id=r.reaction_id, product_nuclide=r.product_nuclide,
        beam_energy_mev=r.beam_energy_mev, exit_energy_mev=r.exit_energy_mev,
        current_ua=r.current_ua, irradiation_time_min=r.irradiation_time_min,
        saturation_yield_mbq_ua=round(r.saturation_yield_mbq_ua, 1),
        saturation_yield_gbq_ua=round(r.saturation_yield_mbq_ua / 1000.0, 3),
        eob_activity_gbq=round(r.eob_activity_gbq, 3),
        eob_activity_gbq_uncertainty=round(r.eob_activity_gbq * r.relative_uncertainty, 3),
        yield_gbq_ua=round(r.yield_gbq_ua, 4),
        saturation_factor=round(r.saturation_factor, 5),
        relative_uncertainty=round(r.relative_uncertainty, 4),
        dataset_id=r.dataset_id, stopping_source=r.stopping_source)


@router.post("/production/burnup", response_model=BurnupResponse)
def compute_burnup(req: BurnupRequest) -> BurnupResponse:
    try:
        r = _service.burnup_compare(
            reaction_id=req.reaction_id, target_id=req.target_id,
            beam_energy_mev=req.beam_energy_mev, current_ua=req.current_ua,
            irradiation_time_min=req.irradiation_time_min,
            beam_spot_cm2=req.beam_spot_cm2, burnup_xs_mb=req.burnup_xs_mb)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return BurnupResponse(**r)


@router.post("/production/burnup-multizone", response_model=BurnupMultizoneResponse)
def compute_burnup_multizone(req: BurnupMultizoneRequest) -> BurnupMultizoneResponse:
    """Quemado del blanco 1D: N capas axiales con atenuación del flujo y
    Bateman con término de quemado por capa (n_zones=1 ≈ grupo único)."""
    try:
        r = _service.burnup_multizone(
            reaction_id=req.reaction_id, target_id=req.target_id,
            beam_energy_mev=req.beam_energy_mev, current_ua=req.current_ua,
            irradiation_time_min=req.irradiation_time_min,
            beam_spot_cm2=req.beam_spot_cm2, n_zones=req.n_zones,
            burnup_xs_max_mb=req.burnup_xs_max_mb)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return BurnupMultizoneResponse(**r)


@router.post("/production/burnup-2d", response_model=BurnupRadialResponse)
def compute_burnup_radial(req: BurnupRadialRequest) -> BurnupRadialResponse:
    """Quemado del blanco 2D: depleción radial bajo haz gaussiano, con el
    EOB 1D (flujo uniforme) de referencia calculado con idénticos
    parámetros. La diferencia EOB_1D − EOB_2D es la corrección radial."""
    try:
        r = _service.burnup_radial(
            reaction_id=req.reaction_id, target_id=req.target_id,
            beam_energy_mev=req.beam_energy_mev, current_ua=req.current_ua,
            irradiation_time_min=req.irradiation_time_min,
            beam_spot_cm2=req.beam_spot_cm2,
            beam_sigma_cm=req.beam_sigma_cm, n_rings=req.n_rings,
            burnup_xs_max_mb=req.burnup_xs_max_mb)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return BurnupRadialResponse(**r)


@router.post("/thermal/target", response_model=ThermalTargetResponse)
def compute_thermal_target(req: ThermalTargetRequest) -> ThermalTargetResponse:
    """Modelo térmico reducido (analítico estacionario): conducción axial
    + película de convección, con pico gaussiano del haz."""
    try:
        r = _service.thermal_target(
            beam_energy_mev=req.beam_energy_mev, current_ua=req.current_ua,
            beam_spot_cm2=req.beam_spot_cm2,
            target_thickness_cm=req.target_thickness_cm,
            conductivity_w_cm_k=req.conductivity_w_cm_k,
            film_coeff_w_cm2_k=req.film_coeff_w_cm2_k,
            coolant_temp_k=req.coolant_temp_k, t_limit_k=req.t_limit_k,
            beam_sigma_cm=req.beam_sigma_cm)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ThermalTargetResponse(**r)


@router.get("/elmer/status")
def elmer_status() -> dict:
    """Estado honesto del acoplamiento FEM Elmer (patrón TALYS/veraPDF):
    available=false si el binario no está instalado — nunca se simula."""
    return _service.elmer_status()


@router.post("/elmer/thermal/compare", response_model=ElmerCompareResponse)
def elmer_thermal_compare(req: ElmerCompareRequest) -> ElmerCompareResponse:
    """Comparación FEM (Elmer, ecuación del calor 2D axisimétrica) contra
    el modelo reducido analítico para el mismo caso físico."""
    try:
        r = _service.elmer_thermal_compare(
            reaction_id=req.reaction_id, target_id=req.target_id,
            irradiation_time_min=req.irradiation_time_min,
            beam_energy_mev=req.beam_energy_mev, current_ua=req.current_ua,
            beam_spot_cm2=req.beam_spot_cm2,
            target_thickness_cm=req.target_thickness_cm,
            conductivity_w_cm_k=req.conductivity_w_cm_k,
            film_coeff_w_cm2_k=req.film_coeff_w_cm2_k,
            coolant_temp_k=req.coolant_temp_k,
            beam_sigma_cm=req.beam_sigma_cm)
    except ElmerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ElmerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ElmerCompareResponse(**r)


@router.post("/elmer/thermomechanical",
             response_model=ElmerThermomechanicalResponse)
def elmer_thermomechanical(
        req: ElmerThermomechanicalRequest) -> ElmerThermomechanicalResponse:
    """EDS cap. 18: análisis termo-mecánico acoplado (18.13) — temperatura,
    tensión de von Mises y desplazamiento (18.12) con puerta 8.11 y
    Material Library (18.8/18.14). 503 sin binario, 422 sin puerta."""
    try:
        r = _service.elmer_thermomechanical(
            reaction_id=req.reaction_id, target_id=req.target_id,
            irradiation_time_min=req.irradiation_time_min,
            beam_energy_mev=req.beam_energy_mev, current_ua=req.current_ua,
            material_id=req.material_id,
            beam_spot_cm2=req.beam_spot_cm2,
            target_thickness_cm=req.target_thickness_cm,
            conductivity_w_cm_k=req.conductivity_w_cm_k,
            film_coeff_w_cm2_k=req.film_coeff_w_cm2_k,
            coolant_temp_k=req.coolant_temp_k,
            beam_sigma_cm=req.beam_sigma_cm)
    except ElmerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ElmerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ElmerThermomechanicalResponse(**r)


@router.get("/mc/status")
def mc_status() -> dict:
    """Estado honesto del Monte Carlo Interface (cap. 19)."""
    return _service.mc_status()


@router.post("/mc/target", response_model=MonteCarloResponse)
def monte_carlo_target(req: MonteCarloRequest) -> MonteCarloResponse:
    """EDS cap. 19: simulación Monte Carlo del blanco con OpenGATE/Geant4
    reales — deposición de energía, dosis, métricas estadísticas (19.20)
    y comparación independiente con el modelo determinista (19.14).
    503 sin motor, 422 si el caso no supera la validación 19.21."""
    try:
        r = _service.monte_carlo_target(
            reaction_id=req.reaction_id, target_id=req.target_id,
            beam_energy_mev=req.beam_energy_mev, current_ua=req.current_ua,
            n_histories=req.n_histories, n_batches=req.n_batches,
            physics_list=req.physics_list,
            target_radius_cm=req.target_radius_cm,
            target_thickness_cm=req.target_thickness_cm,
            beam_radius_cm=req.beam_radius_cm, seed=req.seed,
            operador=req.operador, motivo=req.motivo)
    except GateUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except GateError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return MonteCarloResponse(**r)


@router.get("/reactions")
def list_supported() -> dict:
    return {
        "reactions": [
            {"reaction_id": k, "notation": v["notation"], "product": v["product"],
             "targets": v["targets"]} for k, v in REACTIONS.items()],
        "targets": [
            {"target_id": k, "label": t.label,
             "stopping_material": t.stopping_material,
             "default_enrichment": t.enrichment} for k, t in TARGET_CATALOG.items()],
    }


@router.get("/stopping-power")
def stopping_power(material: str = "h2o", e_min: float = 1.0,
                   e_max: float = 30.0, step: float = 1.0) -> dict:
    if material not in ("h2o", "o2", "n2", "zn68"):
        raise HTTPException(status_code=422, detail="material debe ser h2o, o2, n2 o zn68")
    curve = _service.stopping_curve(material, e_min, e_max, step)
    return {"material": material, "source": _service._stopping.source_label(),
            "points": curve}


@router.get("/target-range")
def target_range(material: str = "h2o", energy_mev: float = 18.0) -> dict:
    return {"material": material, "energy_mev": energy_mev,
            "range_g_cm2": round(_service.target_range(material, energy_mev), 5)}
