"""
Tests del Burnup Engine radial 2D y del modelo térmico reducido:
propiedades físicas (normalización gaussiana, cota EOB_2D ≤ EOB_1D,
límite uniforme), exactitud analítica del térmico y API.
"""
from __future__ import annotations

import math

import pytest

from app.main import DATA_DIR, app
from app.application.production_service import ProductionService
from app.domain.burnup_radial import (BurnupRadialCalculator,
                                      gaussian_peak_factor)
from app.domain.entities import MB_PER_CM2, PROTONS_PER_SECOND_PER_UA
from app.domain.thermal_reduced import beam_power_w, thermal_reduced
from app.infrastructure.repositories.local_reaction_data import \
    LocalReactionDataProvider
from app.infrastructure.stopping.factory import build_stopping_provider
from fastapi.testclient import TestClient

client = TestClient(app)
service = ProductionService(
    stopping=build_stopping_provider(DATA_DIR / "stopping"),
    rxn=LocalReactionDataProvider(DATA_DIR),
)

BASE = dict(reaction_id="o18_p_n_f18", target_id="h2_18o",
            beam_energy_mev=16.5, current_ua=37.0,
            irradiation_time_min=60.0, beam_spot_cm2=1.0)


# --- factor de pico gaussiano (forma cerrada) ------------------------------

def test_peak_factor_tiende_a_uno_para_sigma_grande():
    r = math.sqrt(1.0 / math.pi)
    f = gaussian_peak_factor(r, sigma_cm := 50.0 * r)
    assert 1.0 < f < 1.01
    assert sigma_cm > r


def test_peak_factor_sigma_igual_radio():
    # f = R² / (2σ²(1−e^{−R²/2σ²})) con σ = R → 1 / (2(1−e^{−1/2}))
    f = gaussian_peak_factor(1.0, 1.0)
    assert f == pytest.approx(1.0 / (2.0 * (1.0 - math.exp(-0.5))), rel=1e-12)


def test_peak_factor_crece_al_estrechar_sigma():
    r = math.sqrt(1.0 / math.pi)
    fs = [gaussian_peak_factor(r, s) for s in (0.5 * r, 0.3 * r, 0.2 * r)]
    assert all(b > a for a, b in zip(fs, fs[1:]))


# --- propiedades del modelo radial ------------------------------------------

def _radial(**over):
    kw = dict(BASE) | dict(beam_sigma_cm=0.15, n_rings=20)
    kw.update(over)
    return service.burnup_radial(**kw)


def test_pesos_anillos_suman_uno():
    r = _radial()
    assert sum(g["production_weight"] for g in r["rings"]) == \
        pytest.approx(1.0, abs=1e-12)


def test_flujo_medio_coherente_con_1d():
    # φ_mean = P/A exactamente (misma corriente y área que el modelo 1D)
    r = _radial()
    phi_mean = PROTONS_PER_SECOND_PER_UA * BASE["current_ua"] \
        / BASE["beam_spot_cm2"]
    assert r["flux_mean_cm2_s"] == pytest.approx(phi_mean, rel=1e-12)
    assert r["flux_peak_cm2_s"] > r["flux_mean_cm2_s"]


def test_deplecion_maxima_en_el_eje():
    r = _radial()
    deps = [g["depletion_fraction"] for g in r["rings"]]
    assert deps[0] == max(deps)
    assert all(a >= b for a, b in zip(deps, deps[1:]))  # monótona radial


def test_eob_2d_no_supera_al_1d():
    # La depleción se concentra en el eje → pérdida extra respecto al 1D
    r = _radial()
    assert r["eob_2d_gbq"] <= r["eob_1d_gbq"] + 1e-9
    assert r["loss_vs_1d_gbq"] >= 0.0
    assert r["eob_ideal_gbq"] >= r["eob_1d_gbq"] >= r["eob_2d_gbq"]


def test_limite_perfil_plano_reproduce_el_1d_aprox():
    # σ >> R: gaussiana casi plana → el radial converge al uniforme
    r = _radial(beam_sigma_cm=50.0)
    assert r["peak_factor"] == pytest.approx(1.0, abs=1e-3)
    assert abs(r["eob_2d_gbq"] - r["eob_1d_gbq"]) / r["eob_1d_gbq"] < 0.02


def test_sigma_menor_mayor_perdida():
    r_wide = _radial(beam_sigma_cm=0.5)
    r_tight = _radial(beam_sigma_cm=0.10)
    assert r_tight["loss_vs_1d_gbq"] > r_wide["loss_vs_1d_gbq"]


def test_convergencia_en_numero_de_anillos():
    r20 = _radial(n_rings=20)
    r100 = _radial(n_rings=100)
    assert abs(r20["eob_2d_gbq"] - r100["eob_2d_gbq"]) / r100["eob_2d_gbq"] \
        < 0.01


def test_validaciones_dominio():
    calc = BurnupRadialCalculator(LocalReactionDataProvider(DATA_DIR))
    with pytest.raises(ValueError):
        calc.compute(reaction_id="o18_p_n_f18", beam_energy_mev=16.5,
                     current_ua=37.0, irradiation_time_min=60.0,
                     beam_spot_cm2=0.0, beam_sigma_cm=0.15, n_rings=10,
                     burnup_xs_eff_mb=100.0, eob_ideal_gbq=1.0,
                     eob_1d_gbq=1.0)
    with pytest.raises(ValueError):
        calc.compute(reaction_id="o18_p_n_f18", beam_energy_mev=16.5,
                     current_ua=37.0, irradiation_time_min=60.0,
                     beam_spot_cm2=1.0, beam_sigma_cm=0.15, n_rings=0,
                     burnup_xs_eff_mb=100.0, eob_ideal_gbq=1.0,
                     eob_1d_gbq=1.0)
    with pytest.raises(ValueError):
        # σ ridículamente pequeña respecto al spot
        _radial(beam_sigma_cm=1e-6)


# --- modelo térmico reducido (exactitud analítica) ---------------------------

def test_beam_power_exacto():
    # 1 MeV · 1 µA = 1 W
    assert beam_power_w(18.0, 75.0) == pytest.approx(1350.0)
    with pytest.raises(ValueError):
        beam_power_w(0.0, 10.0)


def test_termico_uniforme_exacto():
    t = thermal_reduced(beam_energy_mev=18.0, current_ua=50.0,
                        beam_spot_cm2=1.0, target_thickness_cm=0.5,
                        conductivity_w_cm_k=0.006, film_coeff_w_cm2_k=0.5,
                        coolant_temp_k=293.15, t_limit_k=373.15)
    q = 18.0 * 50.0  # W/cm² (uniforme)
    assert t.heat_flux_peak_w_cm2 == pytest.approx(q)
    assert t.delta_t_conduction_k == pytest.approx(q * 0.5 / 0.006)
    assert t.delta_t_film_k == pytest.approx(q / 0.5)
    assert t.t_peak_k == pytest.approx(293.15 + q * (0.5 / 0.006 + 1 / 0.5))
    assert not t.within_limit  # 900 W/cm² supera con creces la ebullición


def test_termico_pico_gaussiano_y_margen():
    t = thermal_reduced(beam_energy_mev=18.0, current_ua=20.0,
                        beam_spot_cm2=1.0, target_thickness_cm=0.5,
                        conductivity_w_cm_k=0.006, film_coeff_w_cm2_k=0.5,
                        coolant_temp_k=293.15, t_limit_k=373.15,
                        beam_sigma_cm=0.15)
    assert t.peak_factor > 1.5
    assert t.t_peak_k > t.t_mean_k
    # max_current satura exactamente el límite térmico
    t_lim = thermal_reduced(beam_energy_mev=18.0, current_ua=t.max_current_ua,
                            beam_spot_cm2=1.0, target_thickness_cm=0.5,
                            conductivity_w_cm_k=0.006,
                            film_coeff_w_cm2_k=0.5, coolant_temp_k=293.15,
                            t_limit_k=373.15, beam_sigma_cm=0.15)
    assert t_lim.t_peak_k == pytest.approx(373.15, rel=1e-9)
    assert t_lim.within_limit


def test_termico_validaciones():
    with pytest.raises(ValueError):
        thermal_reduced(beam_energy_mev=18.0, current_ua=20.0,
                        beam_spot_cm2=0.0, target_thickness_cm=0.5,
                        conductivity_w_cm_k=0.006, film_coeff_w_cm2_k=0.5,
                        coolant_temp_k=293.15, t_limit_k=373.15)
    with pytest.raises(ValueError):
        thermal_reduced(beam_energy_mev=18.0, current_ua=20.0,
                        beam_spot_cm2=1.0, target_thickness_cm=0.5,
                        conductivity_w_cm_k=0.006, film_coeff_w_cm2_k=0.5,
                        coolant_temp_k=293.15, t_limit_k=290.0)


# --- API ---------------------------------------------------------------------

def test_api_burnup_2d():
    resp = client.post("/api/v1/production/burnup-2d",
                       json=dict(BASE, beam_sigma_cm=0.15, n_rings=15))
    assert resp.status_code == 200
    d = resp.json()
    assert d["model"] == "radial gaussian depletion (2D)"
    assert len(d["rings"]) == 15
    assert d["eob_2d_gbq"] <= d["eob_1d_gbq"] <= d["eob_ideal_gbq"]
    assert d["depletion_max"] >= d["depletion_weighted"]


def test_api_burnup_2d_validacion():
    resp = client.post("/api/v1/production/burnup-2d",
                       json=dict(BASE, beam_sigma_cm=0.15,
                                 reaction_id="inexistente"))
    assert resp.status_code == 422


def test_api_thermal_target():
    resp = client.post("/api/v1/thermal/target", json={
        "beam_energy_mev": 18.0, "current_ua": 40.0, "beam_spot_cm2": 1.0,
        "target_thickness_cm": 0.5, "conductivity_w_cm_k": 0.006,
        "film_coeff_w_cm2_k": 0.5, "coolant_temp_k": 293.15,
        "t_limit_k": 373.15, "beam_sigma_cm": 0.15})
    assert resp.status_code == 200
    d = resp.json()
    assert d["beam_power_w"] == pytest.approx(720.0)
    assert d["t_peak_k"] > d["t_mean_k"] > 293.15
    assert d["max_current_ua"] > 0.0
