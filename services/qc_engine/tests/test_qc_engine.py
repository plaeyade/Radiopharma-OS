"""
Tests del QC Engine: física de decaimiento, ajuste de vida media,
detección de impurezas y reglas de aceptación.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.application.qc_service import QcService
from app.domain.decay_physics import (decay_correction,
                                      decay_correction_uncertainty,
                                      fit_half_life)
from app.domain.entities import ActivityMeasurement, QcStatus

client = TestClient(app)
service = QcService(nds_url="")     # fallback DDEP local, sin red

HL_F18 = 109.77


# ---------------- decay correction ----------------

def test_decay_correction_una_vida_media():
    assert math.isclose(decay_correction(100.0, HL_F18, HL_F18), 50.0, rel_tol=1e-9)


def test_decay_correction_retroceso():
    fwd = decay_correction(100.0, HL_F18, 60.0, to_future=True)
    back = decay_correction(fwd, HL_F18, 60.0, to_future=False)
    assert math.isclose(back, 100.0, rel_tol=1e-9)


def test_incertidumbre_crece_con_dt():
    """El término de incertidumbre de la vida media crece con Δt."""
    u1 = decay_correction_uncertainty(0.02, HL_F18, 30.0)
    u2 = decay_correction_uncertainty(0.02, HL_F18, 300.0)
    assert u2 > u1
    # con vida media exacta, Δt no afecta (solo término de tiempo)
    u3 = decay_correction_uncertainty(0.02, HL_F18, 30.0, half_life_unc_min=0.0)
    u4 = decay_correction_uncertainty(0.02, HL_F18, 300.0, half_life_unc_min=0.0)
    assert math.isclose(u3, u4, rel_tol=1e-9)


# ---------------- half-life fit ----------------

def _serie_pura(hl=HL_F18, a0=100.0, n=8, ruido=0.0, seed=42):
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 120, n)
    a = a0 * np.exp(-math.log(2) * t / hl)
    if ruido:
        a = a * (1 + rng.normal(0, ruido, n))
    return [ActivityMeasurement(float(ti), float(ai)) for ti, ai in zip(t, a)]


def test_ajuste_recupera_vida_media_exacta():
    fit = fit_half_life(_serie_pura(), HL_F18)
    assert math.isclose(fit.half_life_min, HL_F18, rel_tol=1e-6)
    assert fit.within_tolerance
    assert not fit.impurity_suspected


def test_ajuste_con_ruido_dentro_de_tolerancia():
    fit = fit_half_life(_serie_pura(ruido=0.01), HL_F18)
    assert fit.deviation_percent < 5.0
    assert fit.within_tolerance


def test_impureza_detectada():
    """Serie mezcla 18F + 68Ga: no monoexponencial -> impureza sospechada."""
    rng = np.random.default_rng(7)
    t = np.linspace(0, 120, 10)
    a = (80.0 * np.exp(-math.log(2) * t / 109.77)
         + 20.0 * np.exp(-math.log(2) * t / 67.71))
    a = a * (1 + rng.normal(0, 0.005, len(t)))
    serie = [ActivityMeasurement(float(ti), float(ai)) for ti, ai in zip(t, a)]
    fit = fit_half_life(serie, HL_F18)
    assert fit.impurity_suspected or fit.deviation_percent > 5.0


def test_ajuste_requiere_3_puntos():
    with pytest.raises(ValueError):
        fit_half_life(_serie_pura(n=2), HL_F18)


# ---------------- reglas de aceptación ----------------

def test_pack_fdg_pasa():
    r = service.evaluate_product("fdg", "18F", {
        "ph": 6.8, "radiochemical_purity": 0.985, "radionuclidic_purity": 0.9999,
        "kryptofix_222": 1.0, "endotoxins_eu_ml": 5.0, "acetonitrile_mg_dose": 1.0})
    assert r.overall_status == QcStatus.PASS
    assert all(ev.status == QcStatus.PASS for ev in r.rule_evaluations)


def test_pack_fdg_falla_pureza():
    r = service.evaluate_product("fdg", "18F", {
        "ph": 6.8, "radiochemical_purity": 0.90, "radionuclidic_purity": 0.9999,
        "kryptofix_222": 1.0, "endotoxins_eu_ml": 5.0, "acetonitrile_mg_dose": 1.0})
    assert r.overall_status == QcStatus.FAIL


def test_medicion_faltante_es_warning():
    r = service.evaluate_product("fdg", "18F", {"ph": 6.8})
    assert r.overall_status == QcStatus.WARNING


def test_evaluacion_con_serie_vida_media_integrada():
    r = service.evaluate_product(
        "fdg", "18F",
        {"ph": 6.8, "radiochemical_purity": 0.985, "radionuclidic_purity": 0.9999,
         "kryptofix_222": 1.0, "endotoxins_eu_ml": 5.0, "acetonitrile_mg_dose": 1.0},
        half_life_series=_serie_pura())
    assert r.half_life_fit is not None
    assert r.half_life_fit.within_tolerance


# ---------------- API ----------------

def test_api_health():
    assert client.get("/health").status_code == 200


def test_api_decay_correction():
    r = client.post("/api/v1/qc/decay-correction", json={
        "nuclide": "18F", "activity": 100.0, "delta_time_min": 109.77})
    assert r.status_code == 200
    assert math.isclose(r.json()["corrected_activity"], 50.0, rel_tol=1e-3)


def test_api_half_life_fit():
    serie = [{"time_min": float(t), "activity": float(100.0 * math.exp(-math.log(2)*t/109.77))}
             for t in range(0, 121, 15)]
    r = client.post("/api/v1/qc/half-life-fit",
                    json={"nuclide": "18F", "measurements": serie})
    assert r.status_code == 200
    body = r.json()
    assert math.isclose(body["half_life_min"], 109.77, rel_tol=1e-3)
    assert body["within_tolerance"]


def test_api_evaluate_fdg():
    r = client.post("/api/v1/qc/evaluate", json={
        "product": "fdg", "nuclide": "18F",
        "measurements": {"ph": 6.8, "radiochemical_purity": 0.985,
                         "radionuclidic_purity": 0.9999, "kryptofix_222": 1.0,
                         "endotoxins_eu_ml": 5.0, "acetonitrile_mg_dose": 1.0}})
    assert r.status_code == 200
    assert r.json()["overall_status"] == "pass"


def test_api_rules_packs():
    r = client.get("/api/v1/qc/rules")
    assert r.status_code == 200
    assert "fdg" in r.json()
