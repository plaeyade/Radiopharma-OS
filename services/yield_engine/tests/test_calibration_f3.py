"""
Calibration Layer F3 (EDS 17.6, 17.13, 17.20, 17.21, 17.22, 17.25):
K-factor por lote con datos de producción reales — puerta de calidad
predefinida, ajuste incremental, versionado con operador/motivo, auditoría
y descomposición de incertidumbre.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.application.calibration_service import (CalibrationService,
                                                 EquipmentCatalog)
from app.domain.calibration_batch import (K_MAX, K_MIN, U_REL_MAX,
                                          BatchMeasurement, batch_k_factor,
                                          quality_gate)
from app.main import app
from app.presentation.routers import equipment_api, yield_api


def _med(dias, teo, med, unc=0.0, batch="B-001", op="op.1"):
    fecha = (datetime(2026, 1, 1, tzinfo=timezone.utc)
             + timedelta(days=dias)).isoformat()
    return BatchMeasurement(batch_id=batch, fecha=fecha,
                            eob_predicho_gbq=teo, eob_medido_gbq=med,
                            incertidumbre_gbq=unc, operador=op)


# --------------------------------------------------------------------- dominio
class TestBatchKFactor:
    def test_k_exacto(self):
        assert batch_k_factor(9.0, 10.0) == pytest.approx(0.9)

    def test_predicho_cero_error(self):
        with pytest.raises(ValueError):
            batch_k_factor(1.0, 0.0)


class TestQualityGate:
    def test_acepta_medida_buena(self):
        g = quality_gate(_med(0, 10.0, 9.5))
        assert g["accepted"] and g["k"] == pytest.approx(0.95)

    def test_rechaza_k_incoherente(self):
        g = quality_gate(_med(0, 10.0, 10.0 * (K_MAX + 1)))
        assert not g["accepted"]
        assert any("coherencia física" in r for r in g["reasons"])

    def test_rechaza_u_rel_excesiva(self):
        g = quality_gate(_med(0, 10.0, 9.5,
                              unc=9.5 * (U_REL_MAX + 0.01)))
        assert not g["accepted"]
        assert any("incertidumbre relativa" in r for r in g["reasons"])

    def test_rechaza_sin_lote_ni_operador(self):
        g = quality_gate(_med(0, 10.0, 9.5, batch=" ", op=""))
        assert not g["accepted"]
        assert len(g["reasons"]) == 2

    def test_rechaza_valores_no_positivos(self):
        g = quality_gate(_med(0, -1.0, 9.5))
        assert not g["accepted"]


# -------------------------------------------------------------------- servicio
@pytest.fixture
def svc(tmp_path):
    eq = tmp_path / "equipment.json"
    eq.write_text(json.dumps({"cyclotrons": [{
        "id": "eq_a", "fabricante": "X", "modelo": "Y",
        "energia_max_mev": 18, "energia_fija_mev": False,
        "corriente_max_ua": 100,
        "reacciones_tipicas": ["zn68_p_n_ga68"], "notas": ""}]}))
    return CalibrationService(tmp_path / "cal.json", EquipmentCatalog(eq))


class TestServiceF3:
    def test_registro_aceptado_aparece_en_medidas(self, svc):
        r = svc.register_batch_measurement(
            "zn68_p_n_ga68", "eq_a", _med(0, 10.0, 9.5), motivo="prueba")
        assert r["accepted"] and r["k"] == pytest.approx(0.95)
        assert len(svc.batch_measurements("zn68_p_n_ga68", "eq_a")) == 1

    def test_registro_rechazado_no_se_incorpora_pero_se_audita(self, svc):
        r = svc.register_batch_measurement(
            "zn68_p_n_ga68", "eq_a", _med(0, 10.0, 500.0), motivo="sospechoso")
        assert not r["accepted"]
        assert svc.batch_measurements() == []
        audit = svc.audit_log()
        assert len(audit) == 1 and not audit[0]["aceptada"]
        assert audit[0]["motivo"] == "sospechoso"
        assert audit[0]["razones_rechazo"]

    def test_auditoria_incluye_operador_y_evidencia(self, svc):
        svc.register_batch_measurement(
            "zn68_p_n_ga68", "eq_a", _med(0, 10.0, 9.5, op="maria"),
            motivo="validación rutina")
        e = svc.audit_log()[0]
        assert e["usuario"] == "maria"
        assert e["evidencia"]["batch_id"] == "B-001"
        assert e["accion"] == "registro_medida_lote"

    def test_fit_from_batches_incremental(self, svc):
        for d in range(4):
            svc.register_batch_measurement(
                "zn68_p_n_ga68", "eq_a", _med(d, 10.0, 9.5), motivo="rutina")
        m = svc.fit_from_batches("zn68_p_n_ga68", "eq_a",
                                 operador="maria", motivo="recalibración Q3")
        assert m.factor == pytest.approx(0.95)
        assert m.n_points == 4
        assert m.version == 1
        # 17.22/17.25: el ajuste queda auditado con algoritmo y motivo
        e = svc.audit_log()[-1]
        assert e["accion"] == "fit_from_batches"
        assert e["motivo"] == "recalibración Q3"
        assert "WLS" in e["evidencia"]["algoritmo"]

    def test_fit_from_batches_exige_dos_medidas(self, svc):
        svc.register_batch_measurement(
            "zn68_p_n_ga68", "eq_a", _med(0, 10.0, 9.5), motivo="una sola")
        with pytest.raises(ValueError):
            svc.fit_from_batches("zn68_p_n_ga68", "eq_a",
                                 operador="x", motivo="insuficiente")

    def test_persistencia_medidas_y_auditoria(self, svc, tmp_path):
        svc.register_batch_measurement(
            "zn68_p_n_ga68", "eq_a", _med(0, 10.0, 9.5), motivo="m1")
        svc2 = CalibrationService(tmp_path / "cal.json",
                                  EquipmentCatalog(tmp_path / "equipment.json"))
        assert len(svc2.batch_measurements()) == 1
        assert len(svc2.audit_log()) == 1

    def test_apply_descompone_incertidumbre(self, svc):
        for d in range(4):
            svc.register_batch_measurement(
                "zn68_p_n_ga68", "eq_a",
                _med(d, 10.0, 9.5, unc=0.5), motivo="con u")
        svc.fit_from_batches("zn68_p_n_ga68", "eq_a",
                             operador="maria", motivo="para apply")
        prod = {"eob_activity_gbq": 100.0,
                "eob_activity_gbq_uncertainty": 5.0,
                "saturation_yield_mbq_ua": 2000.0}
        out = svc.apply(prod, "zn68_p_n_ga68", "eq_a")
        inc = out["calibration"]["incertidumbre_gbq"]
        assert out["calibration"]["calibrated"]
        assert inc["fisica"] == pytest.approx(5.0)
        assert inc["experimental"] > 0.0
        assert inc["calibracion"] > 0.0
        assert inc["total"] == pytest.approx(
            (inc["fisica"] ** 2 + inc["calibracion"] ** 2) ** 0.5, abs=1e-3)
        # 17.3: el resultado físico puro permanece accesible e inalterado
        assert out["calibration"]["eob_fisico_sin_calibrar_gbq"] == 100.0


# ------------------------------------------------------------------------ API
@pytest.fixture
def api_client(tmp_path):
    """Re-inicializa el router con un almacén aislado (no contamina)."""
    eq = tmp_path / "equipment.json"
    eq.write_text(json.dumps({"cyclotrons": [{
        "id": "eq_a", "fabricante": "X", "modelo": "Y",
        "energia_max_mev": 18, "energia_fija_mev": False,
        "corriente_max_ua": 100,
        "reacciones_tipicas": ["zn68_p_n_ga68"], "notas": ""}]}))
    cal = CalibrationService(tmp_path / "cal.json", EquipmentCatalog(eq))
    equipment_api.init(yield_api._service, cal)
    return TestClient(app)


def _bm(batch="B-100", teo=10.0, med=9.5, unc=0.0, op="maria", dias=0):
    return {"reaction_id": "zn68_p_n_ga68", "equipment_id": "eq_a",
            "batch_id": batch,
            "fecha": (datetime(2026, 1, 1, tzinfo=timezone.utc)
                      + timedelta(days=dias)).isoformat(),
            "eob_predicho_gbq": teo, "eob_medido_gbq": med,
            "incertidumbre_gbq": unc, "operador": op, "motivo": "test"}


class TestApiF3:
    def test_registro_lote_201(self, api_client):
        r = api_client.post("/api/v1/calibration/batch-measurement",
                            json=_bm())
        assert r.status_code == 201
        b = r.json()
        assert b["accepted"] and b["k"] == pytest.approx(0.95)

    def test_registro_rechazado_201_con_razones(self, api_client):
        r = api_client.post("/api/v1/calibration/batch-measurement",
                            json=_bm(med=99999.0))
        assert r.status_code == 201
        b = r.json()
        assert not b["accepted"] and b["reasons"]

    def test_registro_reaccion_desconocida_422(self, api_client):
        p = _bm(); p["reaction_id"] = "nope"
        r = api_client.post("/api/v1/calibration/batch-measurement", json=p)
        assert r.status_code == 422

    def test_listado_medidas(self, api_client):
        for i in range(3):
            api_client.post("/api/v1/calibration/batch-measurement",
                            json=_bm(batch=f"B-{i}", dias=i))
        r = api_client.get(
            "/api/v1/calibration/zn68_p_n_ga68/eq_a/measurements")
        assert r.status_code == 200 and len(r.json()) == 3

    def test_fit_from_batches_endpoint(self, api_client):
        for i in range(4):
            api_client.post("/api/v1/calibration/batch-measurement",
                            json=_bm(batch=f"B-{i}", dias=i))
        r = api_client.post("/api/v1/calibration/fit-from-batches",
                            json={"reaction_id": "zn68_p_n_ga68",
                                  "equipment_id": "eq_a",
                                  "operador": "maria",
                                  "motivo": "recalibración"})
        assert r.status_code == 200
        assert r.json()["factor"] == pytest.approx(0.95)

    def test_fit_from_batches_sin_datos_422(self, api_client):
        r = api_client.post("/api/v1/calibration/fit-from-batches",
                            json={"reaction_id": "zn68_p_n_ga68",
                                  "equipment_id": "eq_a",
                                  "operador": "maria", "motivo": "vacío"})
        assert r.status_code == 422

    def test_audit_endpoint(self, api_client):
        api_client.post("/api/v1/calibration/batch-measurement", json=_bm())
        api_client.post("/api/v1/calibration/batch-measurement",
                        json=_bm(med=0.0 if False else 99999.0))
        r = api_client.get("/api/v1/calibration/audit")
        assert r.status_code == 200
        entradas = r.json()
        assert len(entradas) == 2
        assert entradas[0]["aceptada"] and not entradas[1]["aceptada"]
        assert all(e["motivo"] for e in entradas)
