"""
Tests del QC Release (EDS Vol. II, cap. 25): especificaciones
versionadas, Validation Engine (25.11) y Release Engine (25.12).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.application.qc_release_service import (ProtocoloQcNoEncontrado,
                                                QcReleaseCatalog,
                                                QcReleaseService)
from app.domain.qc_release import QcInvalido
from app.main import app


@pytest.fixture()
def svc() -> QcReleaseService:
    return QcReleaseService()


def _resultados_ok() -> dict:
    return {
        "identidad_radionucleidica": 109.7,
        "pureza_radionucleidica_pct": 99.9,
        "pureza_radioquimica_pct": 98.0,
        "ph": 6.5,
        "apariencia_score": 1.0,
        "actividad_gbq": 7.4,
        "k222_ppm": 12.0,
        "acetonitrilo_ppm": 100.0,
    }


class TestCatalogo:
    def test_carga_protocolo_y_specs(self, svc):
        p = svc.catalog.protocol("fdg_18f_qc")
        assert p.version == "1.0.0"
        assert len(p.ensayos_requeridos) == 8
        specs = svc.catalog.specs_vigentes()
        assert specs["ph"].limite_inferior == 4.5
        assert specs["k222_ppm"].limite_superior == 50.0

    def test_protocolo_inexistente(self, svc):
        with pytest.raises(ProtocoloQcNoEncontrado):
            svc.catalog.protocol("no_existe")


class TestValidationEngine:
    def test_todo_conforme(self, svc):
        r = svc.release("fdg_18f_qc", _resultados_ok())
        assert r.n_oos == 0 and r.n_pendientes == 0
        assert all(e.estado in ("conforme", "no_aplicable")
                   for e in r.evaluaciones)

    def test_oos_detectado(self, svc):
        res = _resultados_ok()
        res["ph"] = 9.0
        r = svc.release("fdg_18f_qc", res)
        ph = [e for e in r.evaluaciones if e.parametro == "ph"][0]
        assert ph.estado == "fuera_de_especificacion"
        assert r.n_oos == 1

    def test_pendiente_sin_resultado(self, svc):
        res = _resultados_ok()
        res["k222_ppm"] = None
        r = svc.release("fdg_18f_qc", res)
        k = [e for e in r.evaluaciones if e.parametro == "k222_ppm"][0]
        assert k.estado == "pendiente"
        assert r.n_pendientes == 1

    def test_resultado_sin_ensayo_detiene(self, svc):
        res = _resultados_ok()
        res["parametro_inventado"] = 1.0
        with pytest.raises(QcInvalido):
            svc.release("fdg_18f_qc", res)


class TestReleaseEngine:
    def test_rechazo_con_oos(self, svc):
        res = _resultados_ok()
        res["pureza_radioquimica_pct"] = 90.0  # < 95
        r = svc.release("fdg_18f_qc", res)
        assert r.recomendacion == "rechazo"
        assert any("pureza_radioquimica" in m for m in r.motivos)

    def test_revision_con_pendientes(self, svc):
        res = _resultados_ok()
        del res["actividad_gbq"]
        r = svc.release("fdg_18f_qc", res)
        assert r.recomendacion == "revision"

    def test_liberacion_todo_conforme(self, svc):
        r = svc.release("fdg_18f_qc", _resultados_ok())
        assert r.recomendacion == "liberacion"
        # 25.12: recomendación técnica, no liberación final
        assert "flujo de aprobación" in r.auditoria["nota"]

    def test_auditoria_completa(self, svc):
        r = svc.release("fdg_18f_qc", _resultados_ok(), operador="qc1",
                        motivo="lote L-77", lote="L-77")
        a = r.auditoria
        assert a["operador"] == "qc1" and a["lote"] == "L-77"
        assert a["version"] == "1.0.0"


class TestApi:
    def test_release_endpoint(self):
        c = TestClient(app)
        r = c.post("/api/v1/qc/release", json={
            "protocol_id": "fdg_18f_qc", "resultados": _resultados_ok(),
            "operador": "test"})
        assert r.status_code == 200
        assert r.json()["recomendacion"] == "liberacion"

    def test_release_rechazo_endpoint(self):
        c = TestClient(app)
        res = _resultados_ok()
        res["acetonitrilo_ppm"] = 500.0  # > 410
        r = c.post("/api/v1/qc/release", json={
            "protocol_id": "fdg_18f_qc", "resultados": res, "operador": "t"})
        assert r.status_code == 200
        assert r.json()["recomendacion"] == "rechazo"

    def test_release_protocols_endpoint(self):
        c = TestClient(app)
        r = c.get("/api/v1/qc/release/protocols")
        assert r.status_code == 200
        assert r.json()[0]["protocol_id"] == "fdg_18f_qc"

    def test_protocolo_inexistente_404(self):
        c = TestClient(app)
        r = c.post("/api/v1/qc/release", json={
            "protocol_id": "no_existe", "resultados": {}, "operador": "t"})
        assert r.status_code == 404
