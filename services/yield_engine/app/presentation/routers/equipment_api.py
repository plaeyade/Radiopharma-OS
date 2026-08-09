"""
API del Calibration Layer y del catálogo de equipos multivendor.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.application.calibration_service import CalibrationService
from app.application.production_service import ProductionService
from app.domain.calibration import Measurement
from app.domain.calibration_batch import BatchMeasurement
from app.presentation.schemas import (
    AuditEntryOut, BatchMeasurementIn, BatchMeasurementOut,
    CalibrationFitIn, CalibrationIndicatorsIn, CalibrationIndicatorsOut,
    CalibrationModelOut, CalibratedProductionRequest, EquipmentOut,
    FitFromBatchesIn, ProductionResponseCalibrated)

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


@router.get("/calibration/{reaction_id}/{equipment_id}/at",
            response_model=CalibrationModelOut)
def active_at_when(reaction_id: str, equipment_id: str,
                   when: str = Query(..., examples=["2026-06-01T00:00:00Z"])
                   ) -> CalibrationModelOut:
    """17.11: versión de calibración válida en una fecha dada (auditoría)."""
    try:
        dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422,
                            detail=f"Fecha inválida: {when}")
    m = _cal.get_at(reaction_id, equipment_id, dt)
    if m is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sin calibración de {reaction_id} en {equipment_id} "
                   f"anterior a {when}")
    return CalibrationModelOut(**m)


@router.post("/calibration/indicators",
             response_model=CalibrationIndicatorsOut)
def indicators(req: CalibrationIndicatorsIn) -> CalibrationIndicatorsOut:
    """17.26 + 17.10: indicadores de desempeño (error absoluto/relativo,
    tendencia temporal, estabilidad) y detección de deriva significativa
    (cambio acumulado > 2σ de residuos) sobre pares teórico ↔ medido."""
    medidas = [Measurement(fecha=m.fecha, eob_predicho_gbq=m.eob_predicho_gbq,
                           eob_medido_gbq=m.eob_medido_gbq,
                           incertidumbre_gbq=m.incertidumbre_gbq)
               for m in req.medidas]
    try:
        ind = _cal.indicators(medidas)
        drift = _cal.drift(medidas)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return CalibrationIndicatorsOut(
        n=ind.n, error_abs_mean_gbq=ind.error_abs_mean_gbq,
        error_rel_mean=ind.error_rel_mean, error_rel_max=ind.error_rel_max,
        error_rel_std=ind.error_rel_std,
        trend_slope_rel_per_day=ind.trend_slope_rel_per_day,
        trend_r2=ind.trend_r2, span_days=ind.span_days,
        drift_detected=drift.drift_detected,
        accumulated_rel_change=drift.accumulated_rel_change,
        residual_std=drift.residual_std, drift_threshold=drift.threshold,
        drift_note=drift.note)


@router.post("/calibration/batch-measurement",
             response_model=BatchMeasurementOut, status_code=201)
def register_batch_measurement(req: BatchMeasurementIn) -> BatchMeasurementOut:
    """17.6 + 17.21: registra la medida EOB de un lote real si supera la
    puerta de calidad predefinida. El rechazo también queda auditado (17.25):
    se devuelve 201 con accepted=false y las razones — nada se oculta."""
    medida = BatchMeasurement(
        batch_id=req.batch_id, fecha=req.fecha,
        eob_predicho_gbq=req.eob_predicho_gbq,
        eob_medido_gbq=req.eob_medido_gbq,
        incertidumbre_gbq=req.incertidumbre_gbq, operador=req.operador)
    try:
        r = _cal.register_batch_measurement(
            req.reaction_id, req.equipment_id, medida, motivo=req.motivo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return BatchMeasurementOut(**r)


@router.get("/calibration/{reaction_id}/{equipment_id}/measurements",
            response_model=list[BatchMeasurementOut])
def list_batch_measurements(reaction_id: str,
                            equipment_id: str) -> list[BatchMeasurementOut]:
    """Medidas por lote aceptadas para (reacción, equipo)."""
    out = []
    for m in _cal.batch_measurements(reaction_id, equipment_id):
        out.append(BatchMeasurementOut(**m, accepted=True, reasons=[]))
    return out


@router.post("/calibration/fit-from-batches",
             response_model=CalibrationModelOut)
def fit_from_batches(req: FitFromBatchesIn) -> CalibrationModelOut:
    """17.21 (incremental) + 17.23 (anti-deterioro) + 17.22 (versión con
    operador y motivo): recalcula C con las medidas por lote aceptadas."""
    try:
        m = _cal.fit_from_batches(req.reaction_id, req.equipment_id,
                                  operador=req.operador, motivo=req.motivo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return CalibrationModelOut(
        model_id=m.model_id, reaction_id=m.reaction_id,
        equipment_id=m.equipment_id, version=m.version, factor=m.factor,
        factor_uncertainty=m.factor_uncertainty, n_points=m.n_points,
        chi2_ndf=m.chi2_ndf, status=m.status, fitted_at=m.fitted_at,
        medidas=list(m.medidas))


@router.get("/calibration/audit", response_model=list[AuditEntryOut])
def calibration_audit() -> list[AuditEntryOut]:
    """17.25: registro completo de auditoría de la Calibration Layer."""
    return [AuditEntryOut(**e) for e in _cal.audit_log()]


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
