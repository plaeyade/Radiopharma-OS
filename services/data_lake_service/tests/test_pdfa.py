"""
Tests de la conversión y validación PDF/A-2b del eBR (ISO 19005-2).

Validación estructural interna: XMP de conformidad, OutputIntent ICC,
incrustación de fuentes y preservación del contenido. La validación
formal (veraPDF) se realiza en la ingesta del archivo documental.
"""
from __future__ import annotations

from io import BytesIO

import pikepdf
from pypdf import PdfReader

from app.infrastructure.rendering.ebr_pdf import EbrPdfRenderer
from app.infrastructure.rendering.pdfa import to_pdfa2b, validate_pdfa2b
from tests.test_ebr_pdf import _doc_completo, _texto, client  # noqa: F401
from tests.test_jwt_guard import auth_headers


def _pdfa():
    doc = _doc_completo()
    return doc, to_pdfa2b(EbrPdfRenderer().render(doc),
                          title=f"eBR {doc.batch['batch_id']}")


# ---------------- conversión ----------------

def test_pdfa_version_17_y_valido():
    _, pdfa = _pdfa()
    assert pdfa[:8] == b"%PDF-1.7"
    assert len(pdfa) > 3000
    # abre sin errores con ambos lectores
    pikepdf.open(BytesIO(pdfa)).close()
    assert len(PdfReader(BytesIO(pdfa)).pages) >= 1


def test_pdfa_xmp_declara_conformidad():
    _, pdfa = _pdfa()
    with pikepdf.open(BytesIO(pdfa)) as pdf:
        xmp = bytes(pdf.Root.Metadata.read_bytes()).decode("utf-8")
    assert "pdfaid:part" in xmp and ">2<" in xmp
    assert "pdfaid:conformance" in xmp and ">B<" in xmp
    assert "eBR B-" in xmp  # dc:title propagado


def test_pdfa_output_intent_icc_rgb():
    _, pdfa = _pdfa()
    with pikepdf.open(BytesIO(pdfa)) as pdf:
        ois = pdf.Root["/OutputIntents"]
        assert len(ois) == 1
        oi = ois[0]
        assert str(oi["/S"]) == "/GTS_PDFA1"
        assert "sRGB" in str(oi["/OutputConditionIdentifier"])
        perfil = oi["/DestOutputProfile"]
        assert int(perfil["/N"]) == 3
        assert len(bytes(perfil.read_bytes())) > 100  # ICC realmente incrustado


def test_pdfa_validador_sin_hallazgos():
    _, pdfa = _pdfa()
    assert validate_pdfa2b(pdfa) == []


def test_pdfa_contenido_preservado():
    doc, pdfa = _pdfa()
    texto = _texto(pdfa)
    assert "Electronic Batch Record" in texto
    assert doc.batch["batch_id"] in texto
    assert "Firmas electrónicas" in texto
    assert "qa.jefe" in texto
    assert doc.integrity["document_hash"] in texto
    # caracteres fuera de WinAnsi que exigen la TTF incrustada
    assert "µA" in texto


def test_pdfa_tamano_acotado():
    """La sobrecarga de ICC+XMP no debe duplicar el documento."""
    doc = _doc_completo()
    base = EbrPdfRenderer().render(doc)
    pdfa = to_pdfa2b(base)
    assert len(pdfa) < len(base) * 2


# ---------------- validador (casos negativos) ----------------

def test_validador_detecta_pdf_plano():
    """El PDF crudo de reportlab (sin conversión) debe dar hallazgos."""
    base = EbrPdfRenderer().render(_doc_completo())
    hallazgos = validate_pdfa2b(base)
    assert any("OutputIntents" in h for h in hallazgos)
    # sin XMP de conformidad (ausencia total o sin pdfaid)
    assert any("XMP" in h or "pdfaid" in h for h in hallazgos)


def test_validador_detecta_fuente_no_incrustada():
    """Un documento con una fuente base-14 real queda detectado."""
    from reportlab.pdfgen import canvas as _canvas
    buf = BytesIO()
    c = _canvas.Canvas(buf)
    c.setFont("Times-Roman", 12)  # base-14 sin alias: no incrustada
    c.drawString(72, 720, "texto con fuente base")
    c.save()
    hallazgos = validate_pdfa2b(buf.getvalue())
    assert any("fuente no incrustada" in h for h in hallazgos)


def test_validador_rechaza_no_pdf():
    assert validate_pdfa2b(b"esto no es pdf") == ["no es un documento PDF"]


# ---------------- API ----------------

def test_api_pdf_es_pdfa2b_conforme(client):  # noqa: F811
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
    assert "PDF/A-2b" in p.headers["x-pdf-conformance"]
    assert p.content[:8] == b"%PDF-1.7"
    assert validate_pdfa2b(p.content) == []
    assert bid in _texto(p.content)
