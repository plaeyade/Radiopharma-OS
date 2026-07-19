"""
Router REST del Yield Engine.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.application.production_service import ProductionService, REACTIONS
from app.application.target_catalog import TARGET_CATALOG
from app.presentation.schemas import (BurnupMultizoneRequest,
                                      BurnupMultizoneResponse, BurnupRequest,
                                      BurnupResponse, ProductionRequest,
                                      ProductionResponse)

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
