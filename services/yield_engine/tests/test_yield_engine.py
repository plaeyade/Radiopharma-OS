"""
Tests del Yield Engine: física de blanco grueso y validación 18F.

Referencia de validación: Hess et al., Radiochim. Acta 89 (2001) 357
(EXFOR D4095), Tabla 4 - rendimientos a saturación para blanco 18O 100%.
"""
from __future__ import annotations

import math
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, DATA_DIR
from app.application.production_service import ProductionService
from app.application.target_catalog import TARGET_CATALOG
from app.infrastructure.repositories.local_reaction_data import LocalReactionDataProvider
from app.infrastructure.stopping.factory import build_stopping_provider

client = TestClient(app)

service = ProductionService(
    stopping=build_stopping_provider(DATA_DIR / "stopping"),
    rxn=LocalReactionDataProvider(DATA_DIR),
)

# Hess et al. 2001, Tabla 4 (gas 18O 100%, saturación, MBq/µA)
HESS_REFERENCE = {6.0: 2209.0, 10.0: 6871.0, 14.0: 11004.0, 18.0: 13454.0, 20.0: 14228.0}

LAMBDA_F18 = math.log(2) / (109.77 * 60.0)


def test_stopping_power_agua_10mev():
    s = service._stopping.stopping_power("h2o", 10.0)
    # Bethe-Bloch para agua a 10 MeV ~45.7 MeV·cm²/g; ATIMA ~47
    assert 43.0 < s < 50.0


def test_rango_proton_18mev_agua():
    r = service._stopping.range_g_cm2("h2o", 18.0)
    # rango CSDA 18 MeV en agua ~0.34 g/cm²
    assert 0.30 < r < 0.40


def test_rendimiento_gas_vs_hess():
    """Validación contra literatura publicada: desviación < 8%."""
    target = TARGET_CATALOG["o2_18"]
    for e_mev, ref in HESS_REFERENCE.items():
        res = service.compute(
            reaction_id="o18_p_n_f18", target_id="o2_18",
            beam_energy_mev=e_mev, current_ua=1.0,
            irradiation_time_min=600.0, enrichment=1.0)
        got = res.saturation_yield_mbq_ua
        desv = abs(got - ref) / ref
        assert desv < 0.08, f"E={e_mev}: motor={got:.0f} vs Hess={ref:.0f} ({desv:.1%})"


def test_rendimiento_agua_menor_que_gas():
    """En H2^18O hay menos núcleos 18O por gramo: menor rendimiento que en gas."""
    gas = service.compute("o18_p_n_f18", "o2_18", 18.0, 1.0, 600.0)
    agua = service.compute("o18_p_n_f18", "h2_18o", 18.0, 1.0, 600.0)
    assert 0.6 < agua.saturation_yield_mbq_ua / gas.saturation_yield_mbq_ua < 0.9


def test_bajo_umbral_cero():
    res = service.compute("o18_p_n_f18", "o2_18", 2.0, 1.0, 60.0)
    assert res.saturation_yield_mbq_ua == 0.0


def test_factor_saturacion():
    """A t = T1/2 el factor de saturación debe ser exactamente 0.5."""
    res = service.compute("o18_p_n_f18", "h2_18o", 16.0, 10.0, 109.77)
    assert math.isclose(res.saturation_factor, 0.5, rel_tol=1e-3)


def test_escala_lineal_con_corriente():
    a = service.compute("o18_p_n_f18", "h2_18o", 16.0, 10.0, 60.0)
    b = service.compute("o18_p_n_f18", "h2_18o", 16.0, 20.0, 60.0)
    assert math.isclose(b.eob_activity_gbq / a.eob_activity_gbq, 2.0, rel_tol=1e-9)


def test_caso_tipico_f18():
    """Caso típico: 16.5 MeV, 37 µA, 60 min, H2^18O 99.5%."""
    res = service.compute("o18_p_n_f18", "h2_18o", 16.5, 37.0, 60.0)
    # Saturación agua ~9.5 GBq/µA; 1h -> factor 0.315; EOB ~ 9.5*37*0.315 ~ 110 GBq
    assert 90.0 < res.eob_activity_gbq < 135.0
    assert res.relative_uncertainty < 0.15
    assert res.dataset_id == "o18_p_n_f18_iaea2021"


def test_api_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_api_production():
    r = client.post("/api/v1/production", json={
        "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
        "beam_energy_mev": 16.5, "current_ua": 37.0, "irradiation_time_min": 60.0})
    assert r.status_code == 200
    body = r.json()
    assert body["product_nuclide"] == "18F"
    assert 90.0 < body["eob_activity_gbq"] < 135.0


def test_api_reactions_catalog():
    r = client.get("/api/v1/reactions")
    assert r.status_code == 200
    assert r.json()["reactions"][0]["reaction_id"] == "o18_p_n_f18"


def test_api_stopping_power():
    r = client.get("/api/v1/stopping-power?material=h2o&e_min=10&e_max=12&step=1")
    assert r.status_code == 200
    assert len(r.json()["points"]) == 3
