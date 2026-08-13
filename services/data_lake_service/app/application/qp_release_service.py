"""Workflow de liberación QP — Qualified Person (fase 4, GMP; 25.12).

La liberación de un lote de producción clínica es una decisión
organizativa de la Persona Cualificada — nunca automática y nunca una
recomendación técnica del sistema. Este servicio:

- compila el **dossier de decisión** con evidencia REAL: informes QC,
  cadena de firmas electrónicas (21 CFR Part 11), verificación de
  integridad del eBR (hashes) y el gate PDF/A del archivo documental
  (gate interno siempre; veraPDF si el ejecutable está disponible —
  honestamente reportado cuando no lo está);
- ejecuta la **decisión QP** con segregación de funciones: la QP no
  puede liberar un lote que ella misma creó;
- exige integridad eBR verificable para liberar: un registro con hash
  inválido NO se libera;
- registra cada paso en la pista de auditoría del eBR (ALCOA+).

Las reglas GMP de fondo (QC 'pass' obligatorio, inmutabilidad de la
decisión) las mantiene ``BatchService.release_batch`` — este workflow no
las relaja, las refuerza.
"""
from __future__ import annotations

from ..domain.entities import BatchRecord
from ..infrastructure.rendering.pdfa import to_pdfa2b, validate_pdfa2b
from ..infrastructure.rendering.verapdf import validate_with_verapdf
from .batch_service import BatchService
from .ebr_service import EbrService

QP_VERSION = "qp-release-1.0.0"


class QpReleaseService:
    def __init__(self, batches: BatchService, ebr: EbrService,
                 pdf_renderer) -> None:
        self._batches = batches
        self._ebr = ebr
        self._pdf = pdf_renderer

    # -------------------------------------------------- dossier de decisión
    async def dossier(self, batch_id: str) -> dict:
        """Paquete de evidencia REAL para la decisión QP."""
        doc = await self._ebr.generate_ebr(batch_id)  # KeyError si no existe
        integridad = await self._ebr.verify_ebr(batch_id)
        pdf = to_pdfa2b(self._pdf.render(doc), title=f"eBR {batch_id}")
        hallazgos = validate_pdfa2b(pdf)
        verapdf = validate_with_verapdf(pdf)  # honesto: available=False
        return {
            "batch_id": batch_id,
            "estado_lote": doc.batch["status"],
            "decision_vigente": doc.batch["release_status"],
            "creado_por": doc.batch["created_by"],
            "qc_reports": [
                {"qc_id": r["qc_id"], "overall_status": r["overall_status"]}
                for r in doc.qc_reports],
            "firmas": [
                {"meaning": s["meaning"], "signed_by": s["signed_by"]}
                for s in doc.signatures],
            "integridad_ebr": integridad,
            "gate_pdfa": {
                "interno": {"conforme": not hallazgos,
                            "hallazgos": hallazgos},
                "verapdf": {
                    "available": verapdf.available,
                    "compliant": verapdf.compliant,
                    "detalle": verapdf.summary or verapdf.error,
                },
            },
            "version_workflow": QP_VERSION,
        }

    # ---------------------------------------------------- decisión QP real
    async def qp_release(self, batch_id: str, decision: str,
                         qp_username: str,
                         reason: str | None = None) -> BatchRecord:
        """Decisión de liberación de la Persona Cualificada.

        Refuerzos sobre la regla GMP base:
        - segregación de funciones: la QP no libera su propio lote;
        - integridad eBR verificable obligatoria para liberar.
        """
        batch = await self._batches._repo.get(batch_id)
        if batch is None:
            raise LookupError(f"Lote no encontrado: {batch_id}")
        if batch.created_by == qp_username:
            raise ValueError(
                "Segregación de funciones (GMP): la Persona Cualificada "
                "no puede liberar un lote que ella misma creó")
        if decision == "released":
            integridad = await self._ebr.verify_ebr(batch_id)
            if not integridad["all_ok"]:
                fallidos = [c["item"] for c in integridad["checks"]
                            if not c["ok"]]
                raise ValueError(
                    "La integridad del eBR NO es verificable "
                    f"({fallidos}): el lote no se libera")
        record = await self._batches.release_batch(
            batch_id, decision, qp_username, reason)
        await self._ebr.add_event(
            batch_id, qp_username, "qp_release_decision",
            f"Decisión QP: {decision}"
            + (f". Motivo: {reason}" if reason else ""))
        return record
