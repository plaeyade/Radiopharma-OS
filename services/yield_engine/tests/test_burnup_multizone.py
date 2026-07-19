"""
Tests del Burnup Engine multizona 1D: coherencia con grupo único,
perfil axial, convergencia en número de capas y API.
"""
from __future__ import annotations

import math

from app.main import DATA_DIR, app
from app.application.production_service import ProductionService
from app.domain.burnup_calculator import BurnupCalculator
from app.domain.burnup_zones import (DEFAULT_XS_MAX_MB,
                                     BurnupMultizoneCalculator, burnup_xs_mb)
from app.domain.entities import MB_PER_CM2, PROTONS_PER_SECOND_PER_UA
from app.infrastructure.repositories.local_reaction_data import LocalReactionDataProvider
from app.infrastructure.stopping.factory import build_stopping_provider
from fastapi.testclient import TestClient

client = TestClient(app)
service = ProductionService(
    stopping=build_stopping_provider(DATA_DIR / "stopping"),
    rxn=LocalReactionDataProvider(DATA_DIR),
)
rxn = LocalReactionDataProvider(DATA_DIR)
calc_1g = BurnupCalculator()
LAMBDA_F18 = math.log(2) / (109.77 * 60.0)

BASE = dict(reaction_id="o18_p_n_f18", target_id="h2_18o",
            beam_energy_mev=16.5, current_ua=37.0,
            irradiation_time_min=60.0, beam_spot_cm2=1.0)


# --- modelo paramétrico σ_b(E) --------------------------------------------

def test_xs_cero_bajo_umbral():
    th = rxn.get_threshold("o18_p_n_f18")
    assert burnup_xs_mb(th - 1.0, th) == 0.0
    assert burnup_xs_mb(th + 0.01, th) == 0.0   # dentro del margen


def test_xs_monotona_y_acotada():
    th = rxn.get_threshold("o18_p_n_f18")
    xs = [burnup_xs_mb(th + d, th) for d in (1.0, 3.0, 8.0, 15.0, 40.0)]
    assert all(b > a for a, b in zip(xs, xs[1:]))
    assert all(x < DEFAULT_XS_MAX_MB for x in xs)
    assert xs[-1] > 0.99 * DEFAULT_XS_MAX_MB     # tiende a la meseta


# --- coherencia con el modelo de grupo único -------------------------------

def test_una_zona_reproduce_grupo_unico():
    """n_zones=1: Bateman con k = σ_b(E_media)·φ, idéntico al grupo único."""
    r = service.burnup_multizone(**BASE, n_zones=1)
    th = rxn.get_threshold("o18_p_n_f18")
    e_lo = th
    e_mid = 0.5 * (BASE["beam_energy_mev"] + e_lo)
    xs = burnup_xs_mb(e_mid, th)
    phi = PROTONS_PER_SECOND_PER_UA * BASE["current_ua"] / BASE["beam_spot_cm2"]
    k = xs * MB_PER_CM2 * phi

    base = service.compute(BASE["reaction_id"], BASE["target_id"],
                           BASE["beam_energy_mev"], BASE["current_ua"],
                           BASE["irradiation_time_min"])
    esperado_mbq = calc_1g.eob_with_burnup(
        base.saturation_yield_mbq_ua, BASE["current_ua"],
        BASE["irradiation_time_min"], LAMBDA_F18, k)
    assert math.isclose(r["eob_with_burnup_gbq"], esperado_mbq / 1000.0,
                        rel_tol=1e-9)
    assert math.isclose(r["eob_no_burnup_gbq"], base.eob_activity_gbq,
                        rel_tol=1e-9)
    assert r["zones"][0]["flux_attenuation"] == 1.0
    assert math.isclose(r["zones"][0]["burnup_rate_s"], k, rel_tol=1e-12)


# --- comportamiento físico del perfil axial ---------------------------------

def test_orden_eob_y_perdida_positiva():
    r = service.burnup_multizone(**BASE, n_zones=10)
    assert r["eob_with_burnup_gbq"] < r["eob_no_burnup_gbq"]
    assert r["loss_gbq"] > 0.0
    assert math.isclose(r["loss_gbq"],
                        r["eob_no_burnup_gbq"] - r["eob_with_burnup_gbq"],
                        rel_tol=1e-9)


def test_perfil_monotono_decreciente():
    """σ_b cae con la energía y la atenuación solo reduce φ: k_j decrece
    capa a capa; la atenuación es no creciente y empieza en 1."""
    r = service.burnup_multizone(**BASE, n_zones=12)
    ks = [z["burnup_rate_s"] for z in r["zones"]]
    aten = [z["flux_attenuation"] for z in r["zones"]]
    assert all(b <= a for a, b in zip(ks, ks[1:]))
    assert all(b <= a for a, b in zip(aten, aten[1:]))
    assert aten[0] == 1.0 and aten[-1] <= 1.0
    assert r["burnup_rate_max_s"] == ks[0]
    assert r["depletion_max"] >= r["depletion_weighted"] >= 0.0


def test_pesos_suman_uno():
    r = service.burnup_multizone(**BASE, n_zones=10)
    assert math.isclose(sum(z["production_weight"] for z in r["zones"]), 1.0,
                        rel_tol=1e-9)


def test_quemado_tipico_despeciable_en_un_lote():
    """Ciclotrón médico típico: pérdida global < 0.5 % también en 1D."""
    r = service.burnup_multizone(**BASE, n_zones=10)
    loss_pct = 100.0 * r["loss_gbq"] / r["eob_no_burnup_gbq"]
    assert loss_pct < 0.5


def test_convergencia_en_numero_de_capas():
    """El resultado se estabiliza al refinar la malla axial."""
    r10 = service.burnup_multizone(**BASE, n_zones=10)
    r20 = service.burnup_multizone(**BASE, n_zones=20)
    assert math.isclose(r10["eob_with_burnup_gbq"],
                        r20["eob_with_burnup_gbq"], rel_tol=1e-3)


def test_perdida_crece_con_meseta_xs():
    r1 = service.burnup_multizone(**BASE, n_zones=10, burnup_xs_max_mb=800.0)
    r2 = service.burnup_multizone(**BASE, n_zones=10, burnup_xs_max_mb=8000.0)
    assert r2["loss_gbq"] > r1["loss_gbq"]
    assert r2["depletion_weighted"] > r1["depletion_weighted"]


def test_sin_produccion_bajo_umbral():
    r = service.burnup_multizone(**{**BASE, "beam_energy_mev": 2.0}, n_zones=5)
    assert r["eob_no_burnup_gbq"] == 0.0
    assert r["eob_with_burnup_gbq"] == 0.0
    assert r["loss_gbq"] == 0.0
    assert len(r["zones"]) == 5


def test_validaciones():
    import pytest
    with pytest.raises(ValueError):
        service.burnup_multizone(**{**BASE, "reaction_id": "x_y_z"})
    with pytest.raises(ValueError):
        service.burnup_multizone(**{**BASE, "target_id": "n2_gas"})


# --- API --------------------------------------------------------------------

def test_api_burnup_multizone():
    r = client.post("/api/v1/production/burnup-multizone", json={
        **BASE, "n_zones": 12})
    assert r.status_code == 200
    d = r.json()
    assert len(d["zones"]) == 12
    assert d["model"] == "multizone axial depletion (1D)"
    assert d["eob_with_burnup_gbq"] < d["eob_no_burnup_gbq"]
    assert d["zones"][0]["flux_attenuation"] == 1.0
    assert d["burnup_rate_max_s"] >= d["zones"][0]["burnup_rate_s"]


def test_api_reaccion_invalida_422():
    r = client.post("/api/v1/production/burnup-multizone", json={
        **BASE, "reaction_id": "reaccion_inventada"})
    assert r.status_code == 422


def test_api_blanco_incompatible_422():
    r = client.post("/api/v1/production/burnup-multizone", json={
        **BASE, "target_id": "n2_gas"})
    assert r.status_code == 422


def test_api_n_zones_fuera_de_rango_422():
    r = client.post("/api/v1/production/burnup-multizone", json={
        **BASE, "n_zones": 0})
    assert r.status_code == 422
