"""
Router REST del Data Lake Service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from app.application.batch_service import BatchService
from app.application.ebr_service import EbrService
from app.infrastructure.rendering.ebr_pdf import EbrPdfRenderer
from app.infrastructure.rendering.pdfa import to_pdfa2b, validate_pdfa2b
from app.infrastructure.rendering.verapdf import validate_with_verapdf
from app.infrastructure.security.jwt_guard import (Identity, current_identity,
                                                   require_calidad,
                                                   require_operator)
from app.domain.entities import (BeamParameters, DatasetLineage,
                                 ProductionResults)
from app.presentation.schemas import (AuditEventOut, BatchCreateIn, BatchOut,
                                      BeamIn, EbrOut, EbrVerifyOut, EventIn,
                                      EventOut, LineageIn, QcReportCreateIn,
                                      QcReportOut, ReleaseIn, ResultsIn,
                                      SignatureIn, SignatureOut, VeraPdfOut,
                                      VoidIn)

router = APIRouter(prefix="/api/v1/batches", tags=["data-lake"])

_service: BatchService | None = None
_ebr: EbrService | None = None
_pdf = EbrPdfRenderer()


def init(service: BatchService, ebr: EbrService | None = None) -> None:
    global _service, _ebr
    _service = service
    _ebr = ebr


def _out(r) -> BatchOut:
    return BatchOut(
        batch_id=r.batch_id, created_at=r.created_at, created_by=r.created_by,
        reaction_id=r.reaction_id, target_id=r.target_id,
        product_nuclide=r.product_nuclide,
        beam=BeamIn(beam_energy_mev=r.beam.beam_energy_mev,
                    current_ua=r.beam.current_ua,
                    irradiation_time_min=r.beam.irradiation_time_min,
                    enrichment=r.beam.enrichment),
        results=ResultsIn(
            saturation_yield_mbq_ua=r.results.saturation_yield_mbq_ua,
            eob_activity_gbq=r.results.eob_activity_gbq,
            eob_activity_gbq_uncertainty=r.results.eob_activity_gbq_uncertainty,
            saturation_factor=r.results.saturation_factor,
            relative_uncertainty=r.results.relative_uncertainty),
        lineage=LineageIn(dataset_id=r.lineage.dataset_id,
                          dataset_sha256=r.lineage.dataset_sha256,
                          stopping_source=r.lineage.stopping_source),
        status=r.status.value, void_reason=r.void_reason,
        artifact_key=r.artifact_key, record_hash=r.record_hash,
        integrity_ok=BatchService.verify_integrity(r),
        release_status=r.release_status.value, released_by=r.released_by,
        release_reason=r.release_reason, released_at=r.released_at)


@router.post("", response_model=BatchOut, status_code=201)
async def register_batch(payload: BatchCreateIn,
                         identity: Identity = Depends(require_operator)) -> BatchOut:
    record = await _service.register_batch(
        created_by=identity.username,   # ALCOA+ atribuible: siempre del token
        reaction_id=payload.reaction_id, target_id=payload.target_id,
        product_nuclide=payload.product_nuclide,
        beam=BeamParameters(**payload.beam.model_dump()),
        results=ProductionResults(**payload.results.model_dump()),
        lineage=DatasetLineage(**payload.lineage.model_dump()))
    return _out(record)


@router.get("", response_model=list[BatchOut])
async def list_batches(reaction_id: str | None = None, limit: int = 100,
                       _: Identity = Depends(current_identity)) -> list[BatchOut]:
    records = await _service.list_batches(reaction_id=reaction_id, limit=limit)
    return [_out(r) for r in records]


@router.get("/{batch_id}", response_model=BatchOut)
async def get_batch(batch_id: str,
                    _: Identity = Depends(current_identity)) -> BatchOut:
    record = await _service.get_batch(batch_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Lote no encontrado: {batch_id}")
    return _out(record)


@router.post("/{batch_id}/void", response_model=BatchOut)
async def void_batch(batch_id: str, payload: VoidIn,
                     _: Identity = Depends(require_calidad)) -> BatchOut:
    try:
        record = await _service.void_batch(batch_id, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if record is None:
        raise HTTPException(status_code=404, detail=f"Lote no encontrado: {batch_id}")
    return _out(record)


@router.get("/{batch_id}/artifact")
async def get_artifact(batch_id: str,
                       _: Identity = Depends(current_identity)) -> Response:
    record = await _service.get_batch(batch_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Lote no encontrado: {batch_id}")
    try:
        data = _service.get_artifact(record)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(content=data, media_type="application/json")


# ---------------- informes QC ----------------

def _qc_out(r) -> QcReportOut:
    return QcReportOut(
        qc_id=r.qc_id, batch_id=r.batch_id, created_at=r.created_at,
        created_by=r.created_by, product=r.product, nuclide=r.nuclide,
        overall_status=r.overall_status, rules=list(r.rules),
        half_life_fit=r.half_life_fit, record_hash=r.record_hash,
        integrity_ok=(r.compute_hash() == r.record_hash))


@router.post("/{batch_id}/qc-reports", response_model=QcReportOut, status_code=201)
async def register_qc_report(batch_id: str, payload: QcReportCreateIn,
                             identity: Identity = Depends(require_operator)) -> QcReportOut:
    try:
        record = await _service.register_qc_report(
            batch_id=batch_id, created_by=identity.username,
            product=payload.product, nuclide=payload.nuclide,
            overall_status=payload.overall_status, rules=tuple(payload.rules),
            half_life_fit=payload.half_life_fit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _qc_out(record)


@router.get("/{batch_id}/qc-reports", response_model=list[QcReportOut])
async def list_qc_reports(batch_id: str,
                          _: Identity = Depends(current_identity)) -> list[QcReportOut]:
    records = await _service.list_qc_reports(batch_id)
    return [_qc_out(r) for r in records]


# ---------------- liberación GMP ----------------

@router.post("/{batch_id}/release", response_model=BatchOut)
async def release_batch(batch_id: str, payload: ReleaseIn,
                        identity: Identity = Depends(require_calidad)) -> BatchOut:
    try:
        record = await _service.release_batch(
            batch_id, payload.decision, identity.username, payload.reason)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _out(record)


# ---------------- eBR y firmas electrónicas ----------------

def _sig_out(s) -> SignatureOut:
    return SignatureOut(
        signature_id=s.signature_id, batch_id=s.batch_id,
        signed_by=s.signed_by, signed_at=s.signed_at, meaning=s.meaning,
        record_hash_signed=s.record_hash_signed,
        signature_hash=s.signature_hash)


@router.get("/{batch_id}/ebr", response_model=EbrOut)
async def get_ebr(batch_id: str,
                  _: Identity = Depends(current_identity)) -> EbrOut:
    if _ebr is None:
        raise HTTPException(status_code=503, detail="Servicio eBR no configurado")
    try:
        doc = await _ebr.generate_ebr(batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return EbrOut(
        ebr_id=doc.ebr_id, generated_at=doc.generated_at, batch=doc.batch,
        qc_reports=list(doc.qc_reports), signatures=list(doc.signatures),
        audit_trail=[AuditEventOut(timestamp=e.timestamp, actor=e.actor,
                                   action=e.action, detail=e.detail)
                     for e in doc.audit_trail],
        integrity=doc.integrity)


@router.get("/{batch_id}/ebr/verify", response_model=EbrVerifyOut)
async def verify_ebr(batch_id: str,
                     _: Identity = Depends(current_identity)) -> EbrVerifyOut:
    if _ebr is None:
        raise HTTPException(status_code=503, detail="Servicio eBR no configurado")
    try:
        result = await _ebr.verify_ebr(batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return EbrVerifyOut(**result)


@router.get("/{batch_id}/ebr/pdf")
async def get_ebr_pdf(batch_id: str,
                      _: Identity = Depends(current_identity)) -> Response:
    """Copia archivable del eBR en PDF/A-2b (registro regulatorio legible)."""
    if _ebr is None:
        raise HTTPException(status_code=503, detail="Servicio eBR no configurado")
    try:
        doc = await _ebr.generate_ebr(batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    pdf = to_pdfa2b(_pdf.render(doc), title=f"eBR {batch_id}")
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="ebr_{batch_id}.pdf"',
                 "X-PDF-Conformance": "PDF/A-2b (ISO 19005-2)"})


@router.post("/{batch_id}/ebr/validate-pdfa", response_model=VeraPdfOut)
async def validate_ebr_pdfa(batch_id: str,
                            identity: Identity = Depends(require_operator)) -> VeraPdfOut:
    """Gate formal del archivo documental: valida el eBR PDF/A-2b con el
    validador interno (siempre) y con veraPDF si el ejecutable está
    disponible (VERAPDF_CMD o `verapdf` en PATH). El veredicto de veraPDF
    queda registrado en la pista de auditoría del eBR (ALCOA+)."""
    if _ebr is None:
        raise HTTPException(status_code=503, detail="Servicio eBR no configurado")
    try:
        doc = await _ebr.generate_ebr(batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    pdf = to_pdfa2b(_pdf.render(doc), title=f"eBR {batch_id}")

    internal = validate_pdfa2b(pdf)
    r = validate_with_verapdf(pdf)
    registered = False
    if r.compliant is not None:
        veredicto = "CONFORME" if r.compliant else "NO CONFORME"
        detail = (f"Validación formal PDF/A con veraPDF: {veredicto}. "
                  f"{r.summary or r.error}")
        if r.failed_rules:
            detail += " Reglas fallidas: " + "; ".join(r.failed_rules[:5])
        await _ebr.add_event(batch_id, identity.username,
                             "verapdf_validado", detail)
        registered = True
    return VeraPdfOut(
        batch_id=batch_id, available=r.available, compliant=r.compliant,
        profile=r.profile, failed_rules=list(r.failed_rules),
        summary=r.summary, error=r.error, internal_findings=internal,
        registered_in_ebr=registered)


@router.post("/{batch_id}/events", response_model=EventOut, status_code=201)
async def add_event(batch_id: str, payload: EventIn,
                    identity: Identity = Depends(require_operator)) -> EventOut:
    """Declara un evento de proceso en la pista de auditoría del lote.

    Append-only (ALCOA+): el actor se deriva del token y el sello de
    tiempo es del servidor. Uso típico: registrar las desviaciones
    detectadas por el Telemetry Service para que queden en el eBR.
    """
    if _ebr is None:
        raise HTTPException(status_code=503, detail="Servicio eBR no configurado")
    try:
        event = await _ebr.add_event(batch_id, identity.username,
                                     payload.action, payload.detail)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return EventOut(event_id=event.event_id, batch_id=event.batch_id,
                    timestamp=event.timestamp, actor=event.actor,
                    action=event.action, detail=event.detail)


@router.post("/{batch_id}/signatures", response_model=SignatureOut, status_code=201)
async def sign_batch(batch_id: str, payload: SignatureIn,
                     identity: Identity = Depends(current_identity)) -> SignatureOut:
    if _ebr is None:
        raise HTTPException(status_code=503, detail="Servicio eBR no configurado")
    # El firmante debe ser el usuario de la sesión (no se firma a nombre de otro)
    if payload.username != identity.username:
        raise HTTPException(
            status_code=422,
            detail="El firmante debe coincidir con el usuario autenticado de la sesión")
    try:
        sig = await _ebr.sign_batch(batch_id, payload.username,
                                    payload.password, payload.meaning)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _sig_out(sig)
