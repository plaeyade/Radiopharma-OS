"""Tests del workflow de liberación QP (fase 4, GMP; 25.12)."""
from __future__ import annotations

import asyncio

import pytest

from app.application.batch_service import BatchService
from app.application.ebr_service import EbrService
from app.application.qp_release_service import QpReleaseService
from app.infrastructure.rendering.ebr_pdf import EbrPdfRenderer
from tests.test_ebr import (FakeAuth, MemBatches, MemQc, MemSigs, _qc,
                            _record)
from tests.test_events import MemEvents


def run(coro):
    return asyncio.run(coro)


class _StoreVacio:
    async def put(self, *a, **kw):  # no usado en este workflow
        raise NotImplementedError

    async def get(self, *a, **kw):
        raise NotImplementedError


@pytest.fixture()
def qp():
    batches, qc, sigs, events = MemBatches(), MemQc(), MemSigs(), MemEvents()
    batch_svc = BatchService(batches, _StoreVacio(), qc)
    ebr = EbrService(batches, qc, sigs, FakeAuth(), audit_events=events)
    svc = QpReleaseService(batch_svc, ebr, EbrPdfRenderer())
    return svc, batches, qc, sigs, events


def _lote_con_qc_pass(batches, qc):
    rec = _record()
    run(batches.save(rec))
    run(qc.save(_qc(rec.batch_id, status="pass")))
    return rec


# ------------------------------------------------------------- dossier
def test_dossier_compila_evidencia_real(qp):
    svc, batches, qc, sigs, _ = qp
    rec = _lote_con_qc_pass(batches, qc)
    d = run(svc.dossier(rec.batch_id))
    assert d["batch_id"] == rec.batch_id
    assert d["qc_reports"][0]["overall_status"] == "pass"
    assert d["integridad_ebr"]["all_ok"] is True
    # gate PDF/A interno siempre; veraPDF honesto según entorno
    assert "conforme" in d["gate_pdfa"]["interno"]
    assert d["gate_pdfa"]["verapdf"]["available"] in (True, False)
    if not d["gate_pdfa"]["verapdf"]["available"]:
        assert "no encontrado" in d["gate_pdfa"]["verapdf"]["detalle"]


def test_dossier_lote_inexistente(qp):
    svc, *_ = qp
    with pytest.raises(KeyError):
        run(svc.dossier("B-INEXISTENTE"))


# --------------------------------------------------------- decisión QP
def test_qp_libera_con_evidencia_valida(qp):
    svc, batches, qc, _, events = qp
    rec = _lote_con_qc_pass(batches, qc)
    out = run(svc.qp_release(rec.batch_id, "released", "qa.jefe"))
    assert out.release_status.value == "released"
    assert out.released_by == "qa.jefe"
    acciones = [e.action for e in run(events.list_for_batch(rec.batch_id))]
    assert "qp_release_decision" in acciones


def test_qp_no_libera_su_propio_lote(qp):
    svc, batches, qc, *_ = qp
    rec = _record()  # creado por operador.ciclotron
    rec = rec.__class__(**{**rec.__dict__, "created_by": "qa.jefe"})
    run(batches.save(rec))
    run(qc.save(_qc(rec.batch_id, status="pass")))
    with pytest.raises(ValueError, match="Segregación de funciones"):
        run(svc.qp_release(rec.batch_id, "released", "qa.jefe"))


def test_qp_no_libera_sin_qc_pass(qp):
    svc, batches, qc, *_ = qp
    rec = _record("B-20260701-SOLOFAIL")
    run(batches.save(rec))
    run(qc.save(_qc(rec.batch_id, status="fail")))
    with pytest.raises(ValueError, match="GMP"):
        run(svc.qp_release(rec.batch_id, "released", "qa.jefe"))


def test_qp_no_libera_con_integridad_rota(qp):
    svc, batches, qc, *_ = qp
    rec = _lote_con_qc_pass(batches, qc)
    # corromper el hash del registro: la verificación eBR falla
    rec_corrupto = rec.__class__(**{**rec.__dict__,
                                    "record_hash": "0" * 64})
    batches._d[rec.batch_id] = rec_corrupto
    with pytest.raises(ValueError, match="integridad del eBR"):
        run(svc.qp_release(rec.batch_id, "released", "qa.jefe"))


def test_qp_rechazo_exige_motivo(qp):
    svc, batches, qc, *_ = qp
    rec = _lote_con_qc_pass(batches, qc)
    with pytest.raises(ValueError, match="motivo"):
        run(svc.qp_release(rec.batch_id, "rejected", "qa.jefe", "  "))
    out = run(svc.qp_release(rec.batch_id, "rejected", "qa.jefe",
                             "QC fuera de especificación"))
    assert out.release_status.value == "rejected"
