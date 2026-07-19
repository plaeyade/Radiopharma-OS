"""
Tests del render PDF del eBR (copia archivable para archivo regulatorio).
"""
from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from app.application.ebr_service import EbrService
from app.infrastructure.rendering.ebr_pdf import EbrPdfRenderer
from tests.test_ebr import (FakeAuth, MemBatches, MemQc, MemSigs, _qc, _record,
                            client, run)   # noqa: F401  (fixture importada)
from tests.test_jwt_guard import auth_headers


def _doc_completo():
    batches, qc, sigs = MemBatches(), MemQc(), MemSigs()
    svc = EbrService(batches, qc, sigs, FakeAuth())
    rec = _record()
    run(batches.save(rec))
    run(qc.save(_qc(rec.batch_id)))
    run(batches.release(rec.batch_id, "released", "qa.jefe", "Conforme a QC"))
    run(svc.sign_batch(rec.batch_id, "operador.ciclotron",
                       "op-secret", "performed_by"))
    run(svc.sign_batch(rec.batch_id, "supervisor.turno",
                       "sup-secret", "reviewed_by"))
    run(svc.sign_batch(rec.batch_id, "qa.jefe", "qa-secret", "approved_by"))
    return run(svc.generate_ebr(rec.batch_id))


def _texto(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


# ---------------- renderer ----------------

def test_pdf_valido_y_no_trivial():
    pdf = EbrPdfRenderer().render(_doc_completo())
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 3000


def test_pdf_contiene_secciones_regulatorias():
    doc = _doc_completo()
    texto = _texto(EbrPdfRenderer().render(doc))
    assert "Electronic Batch Record" in texto
    assert doc.batch["batch_id"] in texto
    assert "Registro de lote" in texto
    assert "control de calidad" in texto
    assert "Firmas electrónicas" in texto
    assert "Pista de auditoría" in texto
    assert doc.integrity["document_hash"] in texto


def test_pdf_muestra_firmas_y_estados():
    doc = _doc_completo()
    texto = _texto(EbrPdfRenderer().render(doc))
    assert "operador.ciclotron" in texto
    assert "supervisor.turno" in texto
    assert "qa.jefe" in texto
    assert "released" in texto
    assert "PASS" in texto or "pass" in texto


def test_pdf_lote_sin_qc_ni_firmas():
    batches, qc, sigs = MemBatches(), MemQc(), MemSigs()
    svc = EbrService(batches, qc, sigs, FakeAuth())
    rec = _record("B-20260701-SINQC001")
    run(batches.save(rec))
    doc = run(svc.generate_ebr(rec.batch_id))
    pdf = EbrPdfRenderer().render(doc)
    assert pdf[:5] == b"%PDF-"
    texto = _texto(pdf)
    assert "Sin informes QC" in texto
    assert "sin firmas" in texto


def test_pdf_metadatos():
    doc = _doc_completo()
    reader = PdfReader(BytesIO(EbrPdfRenderer().render(doc)))
    assert "eBR" in (reader.metadata.title or "")
    assert "Radiopharma OS" in (reader.metadata.author or "")


# ---------------- API ----------------

def test_api_descargar_pdf(client):   # noqa: F811
    r = client.post("/api/v1/batches", json={
        "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
        "product_nuclide": "18F",
        "beam": {"beam_energy_mev": 16.5, "current_ua": 37.0,
                 "irradiation_time_min": 60.0},
        "results": {"saturation_yield_mbq_ua": 9336.8,
                    "eob_activity_gbq": 108.947,
                    "eob_activity_gbq_uncertainty": 8.095,
                    "saturation_factor": 0.31537,
                    "relative_uncertainty": 0.0743},
        "lineage": {"dataset_id": "o18_p_n_f18_iaea2021",
                    "dataset_sha256": "abc123",
                    "stopping_source": "CATIMA/ATIMA (pycatima 1.981)"}},
        headers=auth_headers("operador", "operador.ciclotron"))
    bid = r.json()["batch_id"]
    client.post(f"/api/v1/batches/{bid}/signatures",
                json={"username": "operador.ciclotron",
                      "password": "op-secret", "meaning": "performed_by"},
                headers=auth_headers("operador", "operador.ciclotron"))

    p = client.get(f"/api/v1/batches/{bid}/ebr/pdf", headers=auth_headers())
    assert p.status_code == 200
    assert p.headers["content-type"] == "application/pdf"
    assert f"ebr_{bid}.pdf" in p.headers["content-disposition"]
    assert p.content[:5] == b"%PDF-"
    assert len(p.content) > 2000


def test_api_pdf_lote_inexistente_404(client):   # noqa: F811
    assert client.get("/api/v1/batches/B-INEXISTENTE/ebr/pdf",
                      headers=auth_headers()).status_code == 404


def test_api_pdf_requiere_token(client):   # noqa: F811
    assert client.get("/api/v1/batches/B-X/ebr/pdf").status_code == 401
