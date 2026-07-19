"""
API del Calibration Layer y del catálogo de equipos multivendor.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.application.calibration_service import CalibrationService
from app.application.production_service import ProductionService
from app.domain.calibration import Measurement
from app.presentation.schemas import (CalibrationFitIn, CalibrationModelOut,
                                      CalibratedProductionRequest, EquipmentOut,
                                      ProductionResponseCalibrated)

router = APIRouter(prefix="/api/v1", tags=["calibration"])

_service: ProductionService | None = None
_cal: CalibrationService | None = None


def init(service: ProductionService, calibration: CalibrationService) -> None:
    global _service, _cal
    _service = service
    _cal = calibration


@router.get("/equipment", response_model=list[EquipmentOut])
def list_equipment() -> list[EquipmentOut]:
    """Catálogo multivendor de ciclotrones (IBA, GE, Best, LBT, ikure…)."""
    return [EquipmentOut(**vars(e)) for e in _cal._catalog.list()]


@router.get("/equipment/{equipment_id}", response_model=EquipmentOut)
def get_equipment(equipment_id: str) -> EquipmentOut:
    try:
        return EquipmentOut(**vars(_cal._catalog.get(equipment_id)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/calibration/fit", response_model=CalibrationModelOut)
def fit(req: CalibrationFitIn) -> CalibrationModelOut:
    """Ajusta y almacena una nueva versión del modelo de calibración
    (factor C = EOB_real / EOB_predicho por WLS con χ² y estado GMP)."""
    medidas = [Measurement(fecha=m.fecha, eob_predicho_gbq=m.eob_predicho_gbq,
                           eob_medido_gbq=m.eob_medido_gbq,
                           incertidumbre_gbq=m.incertidumbre_gbq)
               for m in req.medidas]
    try:
        model = _cal.fit_and_store(req.reaction_id, req.equipment_id, medidas)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return CalibrationModelOut(**{**vars(model),
                                  "medidas": list(model.medidas)})


@router.get("/calibration/models", response_model=list[CalibrationModelOut])
def models(reaction_id: str | None = None,
           equipment_id: str | None = None) -> list[CalibrationModelOut]:
    """Historial versionado de modelos (trazabilidad completa, ALCOA+)."""
    return [CalibrationModelOut(**m)
            for m in _cal.history(reaction_id, equipment_id)]


@router.get("/calibration/{reaction_id}/{equipment_id}",
            response_model=CalibrationModelOut)
def active(reaction_id: str, equipment_id: str) -> CalibrationModelOut:
    m = _cal.get_active(reaction_id, equipment_id)
    if m is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sin modelo de calibración para {reaction_id} en {equipment_id}")
    return CalibrationModelOut(**m)


@router.post("/production/calibrated",
             response_model=ProductionResponseCalibrated)
def production_calibrated(req: CalibratedProductionRequest) -> ProductionResponseCalibrated:
    """Predicción del Physics Twin con el factor de calibración vigente
    aplicado (si existe modelo para esa reacción + equipo)."""
    from app.presentation.routers.yield_api import production_response_dict
    try:
        r = _service.compute(req.reaction_id, req.target_id, req.beam_energy_mev,
                             req.current_ua, req.irradiation_time_min,
                             enrichment=req.enrichment)
        out = _cal.apply(production_response_dict(r),
                         req.reaction_id, req.equipment_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ProductionResponseCalibrated(**out)
