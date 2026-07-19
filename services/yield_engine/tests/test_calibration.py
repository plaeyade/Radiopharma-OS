"""
Tests del Calibration Layer: ajuste WLS del factor C, criterios GMP,
versionado, catálogo multivendor y API.
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.application.calibration_service import (CalibrationService,
                                                 EquipmentCatalog)
from app.domain.calibration import Measurement, classify, fit_factor
from app.main import DATA_DIR, app
from app.presentation.routers import equipment_api

client = TestClient(app)


def _m(ratio: float, u: float = 0.0, pred: float = 100.0) -> Measurement:
    return Measurement(fecha="2026-07-01", eob_predicho_gbq=pred,
                       eob_medido_gbq=ratio * pred, incertidumbre_gbq=u)


# ---------------- ajuste WLS del factor ----------------------------------

def test_fit_wls_recupera_factor_conocido():
    """Con medidas coherentes alrededor de C=0.92, el WLS lo recupera."""
    medidas = [_m(0.92, u=1.0), _m(0.92, u=1.2), _m(0.92, u=0.8)]
    r = fit_factor(medidas)
    assert math.isclose(r.factor, 0.92, rel_tol=1e-9)
    assert r.n_points == 3
    assert r.chi2_ndf < 2.5
    assert r.factor_uncertainty > 0.0


def test_fit_sin_incertidumbres_usa_dispersion_muestral():
    medidas = [_m(0.90), _m(0.94), _m(0.92), _m(0.92)]
    r = fit_factor(medidas)
    assert math.isclose(r.factor, 0.92, rel_tol=1e-9)
    assert math.isclose(r.chi2_ndf, 1.0)


def test_fit_pondera_por_incertidumbre():
    """La medida precisa domina el factor ajustado."""
    medidas = [_m(0.90, u=10.0), _m(0.96, u=0.5)]
    r = fit_factor(medidas)
    assert abs(r.factor - 0.96) < 0.005


def test_fit_chi2_detecta_inconsistencia():
    """Medidas muy dispersas con incertidumbres pequeñas → investigar."""
    medidas = [_m(0.80, u=0.2), _m(1.05, u=0.2), _m(0.85, u=0.2)]
    r = fit_factor(medidas)
    assert r.chi2_ndf > 2.5
    assert r.status == "investigar"


def test_fit_errores():
    with pytest.raises(ValueError):
        fit_factor([_m(1.0)])
    with pytest.raises(ValueError):
        fit_factor([_m(1.0), Measurement(fecha="x", eob_predicho_gbq=0.0,
                                         eob_medido_gbq=1.0)])


def test_classify_reglas_gmp():
    assert classify(1.02, 0.01, 1.0) == "vigente"
    assert classify(0.92, 0.01, 1.0) == "observado"     # >2σ aunque <10 %
    assert classify(1.15, 0.10, 1.0) == "observado"     # >10 %
    assert classify(1.40, 0.01, 1.0) == "investigar"    # >35 %
    assert classify(1.00, 0.01, 3.0) == "investigar"    # χ² alto


# ---------------- servicio: catálogo y versionado -------------------------

@pytest.fixture()
def cal(tmp_path):
    return CalibrationService(tmp_path / "cal.json",
                              EquipmentCatalog(DATA_DIR / "equipment.json"))


def test_catalogo_multivendor(cal):
    ids = {e.id for e in cal._catalog.list()}
    assert {"iba_kiube", "iba_cyclone_30", "iba_cyclone_70", "ge_pettrace",
            "ge_qilin", "best_b15", "best_b70", "lbt_beam", "ikure"} <= ids
    kiube = cal._catalog.get("iba_kiube")
    assert kiube.energia_max_mev == 18.0 and kiube.corriente_max_ua == 300.0
    with pytest.raises(ValueError):
        cal._catalog.get("acelerador_inventado")


def test_versionado_y_activo(cal):
    m1 = cal.fit_and_store("o18_p_n_f18", "iba_kiube", [_m(0.92), _m(0.92)])
    m2 = cal.fit_and_store("o18_p_n_f18", "iba_kiube", [_m(0.95), _m(0.95)])
    assert m1.version == 1 and m2.version == 2
    assert m2.model_id == "CAL-o18_p_n_f18-iba_kiube-v2"
    activo = cal.get_active("o18_p_n_f18", "iba_kiube")
    assert activo["version"] == 2 and activo["factor"] == 0.95
    # otra reacción/equipo: sin modelo
    assert cal.get_active("n14_p_a_c11", "iba_kiube") is None
    assert len(cal.history("o18_p_n_f18")) == 2


def test_persistencia_en_disco(tmp_path):
    store = tmp_path / "cal.json"
    cal1 = CalibrationService(store, EquipmentCatalog(DATA_DIR / "equipment.json"))
    cal1.fit_and_store("o18_p_n_f18", "iba_kiube", [_m(0.92), _m(0.92)])
    cal2 = CalibrationService(store, EquipmentCatalog(DATA_DIR / "equipment.json"))
    assert cal2.get_active("o18_p_n_f18", "iba_kiube")["factor"] == 0.92


def test_apply_sin_modelo(cal):
    prod = {"eob_activity_gbq": 100.0, "saturation_yield_mbq_ua": 2000.0}
    out = cal.apply(prod, "o18_p_n_f18", "iba_kiube")
    assert out["calibration"]["calibrated"] is False
    assert out["eob_activity_gbq"] == 100.0


def test_apply_con_modelo(cal):
    cal.fit_and_store("o18_p_n_f18", "iba_kiube", [_m(0.90), _m(0.90)])
    prod = {"eob_activity_gbq": 100.0, "saturation_yield_mbq_ua": 2000.0}
    out = cal.apply(prod, "o18_p_n_f18", "iba_kiube")
    c = out["calibration"]
    assert c["calibrated"] is True and c["factor"] == 0.90
    assert math.isclose(out["eob_activity_gbq"], 90.0)
    assert c["eob_fisico_sin_calibrar_gbq"] == 100.0


# ---------------- API ------------------------------------------------------

@pytest.fixture()
def api_cal(tmp_path):
    """Re-inicializa el router con un almacén temporal (no ensucia el repo)."""
    from app.main import service
    c = CalibrationService(tmp_path / "api_cal.json",
                           EquipmentCatalog(DATA_DIR / "equipment.json"))
    equipment_api.init(service, c)
    return c


def test_api_equipment(api_cal):
    r = client.get("/api/v1/equipment")
    assert r.status_code == 200 and len(r.json()) >= 9
    r = client.get("/api/v1/equipment/iba_kiube")
    assert r.status_code == 200 and r.json()["fabricante"] == "IBA"
    assert client.get("/api/v1/equipment/no_existe").status_code == 404


def test_api_fit_versionado_y_activo(api_cal):
    body = {"reaction_id": "o18_p_n_f18", "equipment_id": "iba_kiube",
            "medidas": [{"fecha": "2026-07-01", "eob_predicho_gbq": 100.0,
                         "eob_medido_gbq": 92.0},
                        {"fecha": "2026-07-08", "eob_predicho_gbq": 100.0,
                         "eob_medido_gbq": 92.5}]}
    r = client.post("/api/v1/calibration/fit", json=body)
    assert r.status_code == 200
    d = r.json()
    assert d["version"] == 1 and math.isclose(d["factor"], 0.9225, rel_tol=1e-3)
    r = client.get("/api/v1/calibration/o18_p_n_f18/iba_kiube")
    assert r.status_code == 200 and r.json()["version"] == 1
    assert client.get("/api/v1/calibration/n14_p_a_c11/iba_kiube").status_code == 404
    assert len(client.get("/api/v1/calibration/models").json()) == 1


def test_api_fit_validaciones(api_cal):
    r = client.post("/api/v1/calibration/fit", json={
        "reaction_id": "reaccion_inventada", "equipment_id": "iba_kiube",
        "medidas": [{"fecha": "x", "eob_predicho_gbq": 1, "eob_medido_gbq": 1},
                    {"fecha": "y", "eob_predicho_gbq": 1, "eob_medido_gbq": 1}]})
    assert r.status_code == 422
    r = client.post("/api/v1/calibration/fit", json={
        "reaction_id": "o18_p_n_f18", "equipment_id": "equipo_inventado",
        "medidas": [{"fecha": "x", "eob_predicho_gbq": 1, "eob_medido_gbq": 1},
                    {"fecha": "y", "eob_predicho_gbq": 1, "eob_medido_gbq": 1}]})
    assert r.status_code == 422


def test_api_produccion_calibrada(api_cal):
    client.post("/api/v1/calibration/fit", json={
        "reaction_id": "o18_p_n_f18", "equipment_id": "iba_kiube",
        "medidas": [{"fecha": "2026-07-01", "eob_predicho_gbq": 100.0,
                     "eob_medido_gbq": 90.0},
                    {"fecha": "2026-07-08", "eob_predicho_gbq": 100.0,
                     "eob_medido_gbq": 90.0}]})
    r = client.post("/api/v1/production/calibrated", json={
        "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
        "beam_energy_mev": 16.5, "current_ua": 37.0,
        "irradiation_time_min": 60.0, "equipment_id": "iba_kiube"})
    assert r.status_code == 200
    d = r.json()
    assert d["calibration"]["calibrated"] is True
    assert math.isclose(d["eob_activity_gbq"],
                        d["calibration"]["eob_fisico_sin_calibrar_gbq"] * 0.90,
                        rel_tol=1e-3)  # EOB se redondea a 3 decimales
    # equipo sin modelo: predicción física pura
    r = client.post("/api/v1/production/calibrated", json={
        "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
        "beam_energy_mev": 16.5, "current_ua": 37.0,
        "irradiation_time_min": 60.0, "equipment_id": "ge_pettrace"})
    assert r.json()["calibration"]["calibrated"] is False
