"""
Tests del gate formal PDF/A con veraPDF: parseo de informes, comportamiento
sin herramienta, endpoint y registro ALCOA+ del veredicto en el eBR.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.rendering.verapdf import (VeraPdfResult, _parse_report,
                                                  validate_with_verapdf)

SECRET = "dev-secret-change-me-in-production"

REPORT_PASSED = {
    "report": {
        "jobs": [{
            "itemDetails": {"name": "ebr.pdf"},
            "validationResult": [{
                "profileName": "PDF/A-2B validation profile",
                "compliant": True,
                "statement": "PDF file is compliant with Validation Profile requirements",
                "details": {"status": "passed", "passedRules": 141,
                            "failedRules": 0, "passedChecks": 10422,
                            "failedChecks": 0}}]}],
        "summary": {"status": "valid"}}}

REPORT_FAILED = {
    "report": {
        "jobs": [{
            "itemDetails": {"name": "ebr.pdf"},
            "validationResult": [{
                "profileName": "PDF/A-2B validation profile",
                "compliant": False,
                "statement": "PDF file is not compliant with Validation Profile requirements",
                "details": {"status": "failed", "passedRules": 139,
                            "failedRules": 2, "passedChecks": 10400,
                            "failedChecks": 22,
                            "ruleSummaries": [
                                {"ruleStatus": "failed",
                                 "specification": "ISO 19005-2:2011",
                                 "clause": "6.6.2.3",
                                 "description": "Font not embedded"},
                                {"ruleStatus": "passed",
                                 "specification": "ISO 19005-2:2011",
                                 "clause": "6.1.3",
                                 "description": "File trailer"}]}}]}],
        "summary": {"status": "invalid"}}}


# ---------------- parseo de informes --------------------------------------

def test_parse_informe_conforme():
    r = _parse_report(REPORT_PASSED)
    assert r.available and r.compliant is True
    assert "PDF/A-2B" in r.profile and "141" in r.summary


def test_parse_informe_no_conforme():
    r = _parse_report(REPORT_FAILED)
    assert r.available and r.compliant is False
    assert len(r.failed_rules) == 1
    assert "Font not embedded" in r.failed_rules[0]


def test_parse_informe_sin_jobs():
    r = _parse_report({"report": {"jobs": []}})
    assert r.compliant is None and "sin jobs" in r.error


def test_herramienta_no_disponible():
    r = validate_with_verapdf(b"%PDF-fake", cmd="verapdf-inexistente-xyz")
    assert r.available is False and r.compliant is None
    assert "no encontrado" in r.error


def test_flujo_completo_con_cli_simulado(monkeypatch, tmp_path):
    import shutil
    import subprocess
    monkeypatch.setattr(shutil, "which", lambda exe: "/usr/bin/verapdf")

    class _P:
        returncode = 0
        stdout = json.dumps(REPORT_PASSED).encode()
        stderr = b""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _P())
    r = validate_with_verapdf(b"%PDF-1.7 fake")
    assert r.available and r.compliant is True


# ---------------- endpoint + registro ALCOA+ ------------------------------

_PAYLOAD = {
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
                "stopping_source": "CATIMA/ATIMA (pycatima 1.981)"},
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "objects"))
    import importlib
    import app.config as config
    importlib.reload(config)
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def _crear_lote(client) -> str:
    from tests.test_jwt_guard import auth_headers
    r = client.post("/api/v1/batches", json=_PAYLOAD,
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 201
    return r.json()["batch_id"]


def test_endpoint_sin_verapdf_usa_gate_interno(client):
    from tests.test_jwt_guard import auth_headers
    bid = _crear_lote(client)
    r = client.post(f"/api/v1/batches/{bid}/ebr/validate-pdfa",
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is False            # sin CLI en el entorno de tests
    assert d["internal_findings"] == []       # nuestro PDF es conforme internamente
    assert d["registered_in_ebr"] is False


def test_endpoint_con_verapdf_registra_veredicto(client, monkeypatch):
    from tests.test_jwt_guard import auth_headers
    import app.presentation.routers.batches as batches_router
    monkeypatch.setattr(
        batches_router, "validate_with_verapdf",
        lambda pdf: VeraPdfResult(available=True, compliant=True,
                                  profile="PDF/A-2B validation profile",
                                  summary="PDF/A-2B: passed (141 reglas OK, 0 fallidas)"))
    bid = _crear_lote(client)
    r = client.post(f"/api/v1/batches/{bid}/ebr/validate-pdfa",
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 200
    d = r.json()
    assert d["compliant"] is True and d["registered_in_ebr"] is True
    # el veredicto quedó en la pista de auditoría del eBR (ALCOA+)
    r = client.get(f"/api/v1/batches/{bid}/ebr",
                   headers=auth_headers("operador", "operador.ciclotron"))
    acciones = [a["action"] for a in r.json()["audit_trail"]]
    assert "verapdf_validado" in acciones


def test_endpoint_lote_inexistente_404(client):
    from tests.test_jwt_guard import auth_headers
    r = client.post("/api/v1/batches/B-NOPE/ebr/validate-pdfa",
                    headers=auth_headers("operador", "operador.ciclotron"))
    assert r.status_code == 404


def test_reparacion_anchos_mono_en_origen():
    """El PDF/A que emite la plataforma ya sale reparado: reportlab escribe
    hmtx erróneos al subsetear DejaVu Sans Mono; to_pdfa2b los corrige
    (regla ISO 19005-2 §6.2.11.5 que veraPDF exige)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from io import BytesIO
    from app.infrastructure.rendering.fonts import MONO, registrar_fuentes
    from app.infrastructure.rendering.pdfa import (check_width_consistency,
                                                   to_pdfa2b)
    registrar_fuentes()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(MONO, 10)
    c.drawString(72, 750, "hash sha256: 0123456789abcdef — firma eBR")
    c.save()
    raw = buf.getvalue()
    # el PDF crudo de reportlab presenta la discrepancia…
    assert len(check_width_consistency(raw)) > 0
    # …y to_pdfa2b la repara en origen
    assert check_width_consistency(to_pdfa2b(raw)) == []
