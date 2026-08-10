"""
Router REST del QC Engine.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.application.qc_release_service import (ProtocoloQcNoEncontrado,
                                                QcReleaseService)
from app.application.qc_service import QcService
from app.domain.entities import ActivityMeasurement
from app.domain.qc_release import QcInvalido
from app.presentation.schemas import (DecayCorrectionIn, DecayCorrectionOut,
                                      SpcIn, SpcOut, SpcPointOut,
                                      HalfLifeFitIn, HalfLifeFitOut,
                                      QcEvaluateIn, QcParamEvalOut,
                                      QcReleaseIn, QcReleaseOut, QcReportOut,
                                      RuleEvalOut)

_release_service: QcReleaseService | None = None

router = APIRouter(prefix="/api/v1/qc", tags=["qc-engine"])

_service: QcService | None = None


def init(service: QcService) -> None:
    global _service
    _service = service


def _fit_out(f) -> HalfLifeFitOut:
    return HalfLifeFitOut(
        half_life_min=round(f.half_life_min, 3),
        half_life_uncertainty_min=round(f.half_life_uncertainty_min, 4),
        activity_at_t0=round(f.activity_at_t0, 4),
        chi_squared_reduced=round(f.chi_squared_reduced, 3),
        n_points=f.n_points,
        reference_half_life_min=f.reference_half_life_min,
        deviation_percent=round(f.deviation_percent, 2),
        within_tolerance=f.within_tolerance,
        tolerance_percent=f.tolerance_percent,
        impurity_suspected=f.impurity_suspected)


@router.post("/decay-correction", response_model=DecayCorrectionOut)
def decay_correct(payload: DecayCorrectionIn) -> DecayCorrectionOut:
    try:
        r = _service.decay_correct(
            payload.nuclide, payload.activity, payload.delta_time_min,
            payload.to_future, payload.relative_uncertainty)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return DecayCorrectionOut(**r)


@router.post("/half-life-fit", response_model=HalfLifeFitOut)
def half_life_fit(payload: HalfLifeFitIn) -> HalfLifeFitOut:
    try:
        f = _service.verify_half_life(
            payload.nuclide,
            [ActivityMeasurement(m.time_min, m.activity, m.uncertainty)
             for m in payload.measurements],
            payload.tolerance_percent, payload.chi2_threshold)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _fit_out(f)


@router.post("/evaluate", response_model=QcReportOut)
def evaluate(payload: QcEvaluateIn) -> QcReportOut:
    try:
        report = _service.evaluate_product(
            payload.product, payload.nuclide, payload.measurements,
            [ActivityMeasurement(m.time_min, m.activity, m.uncertainty)
             for m in payload.half_life_series] if payload.half_life_series else None,
            payload.tolerance_percent)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return QcReportOut(
        product=report.product, nuclide=report.nuclide,
        overall_status=report.overall_status.value,
        rule_evaluations=[
            RuleEvalOut(
                parameter=ev.rule.parameter, measured=ev.measured,
                status=ev.status.value, detail=ev.detail,
                limits=f"[{ev.rule.min_value}, {ev.rule.max_value}] {ev.rule.unit}",
                source=ev.rule.source)
            for ev in report.rule_evaluations],
        half_life_fit=_fit_out(report.half_life_fit) if report.half_life_fit else None)


@router.post("/spc", response_model=SpcOut)
def spc(payload: SpcIn) -> SpcOut:
    """Carta de control de individuales (Shewhart) con reglas WE/Nelson.

    Trending GMP de un parámetro QC a lo largo de la historia de lotes:
    detecta deriva del proceso antes del OOS. Resultado de apoyo a la
    decisión — nunca sustituye la evaluación técnica (EDS 25.17/26.19).
    """
    try:
        r = _service.spc(payload.values, labels=payload.labels,
                         spec_low=payload.spec_low, spec_high=payload.spec_high)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SpcOut(
        n=r.n, mean=r.mean, sigma=r.sigma, ucl=r.ucl, lcl=r.lcl,
        points=[SpcPointOut(index=p.index, label=p.label, value=p.value,
                            violations=list(p.violations)) for p in r.points],
        in_control=r.in_control, spec_low=r.spec_low, spec_high=r.spec_high,
        cp=r.cp, cpk=r.cpk)


@router.get("/rules")
def list_rule_packs() -> dict:
    return _service.rule_packs()


# ---------------------------------------------------------------------------
# QC Release (EDS Vol. II, cap. 25): Validation Engine 25.11 + Release 25.12
# ---------------------------------------------------------------------------

def init_release(service) -> None:
    global _release_service
    _release_service = service


@router.get("/release/protocols")
def list_qc_protocols() -> list[dict]:
    return [
        {"protocol_id": p.protocol_id,
         "radiopharmaceutical": p.radiopharmaceutical,
         "version": p.version,
         "ensayos_requeridos": list(p.ensayos_requeridos),
         "validated": p.validated, "source": p.source}
        for p in _release_service.catalog.list_protocols()]


@router.post("/release", response_model=QcReleaseOut)
def qc_release(payload: QcReleaseIn) -> QcReleaseOut:
    """Recomendación técnica de liberación (25.12).

    Compara cada resultado contra la especificación vigente (25.10/
    25.11) y consolida: rechazo si algún OOS, revisión si hay
    pendientes, liberación si todo conforme. La decisión definitiva
    sigue el flujo de aprobación organizativo.
    """
    try:
        r = _release_service.release(
            payload.protocol_id, payload.resultados,
            operador=payload.operador, motivo=payload.motivo,
            lote=payload.lote, fecha=payload.fecha)
    except ProtocoloQcNoEncontrado as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except QcInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return QcReleaseOut(
        protocol_id=r.protocol_id, radiopharmaceutical=r.radiopharmaceutical,
        recomendacion=r.recomendacion, motivos=list(r.motivos),
        evaluaciones=[QcParamEvalOut(
            parametro=e.parametro, valor=e.valor, unidades=e.unidades,
            estado=e.estado, spec_version=e.spec_version,
            detalle=e.detalle) for e in r.evaluaciones],
        n_conformes=r.n_conformes, n_oos=r.n_oos,
        n_pendientes=r.n_pendientes, validated=r.validated,
        auditoria=r.auditoria)
