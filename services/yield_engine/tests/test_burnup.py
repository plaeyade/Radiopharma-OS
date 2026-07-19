"""
Tests del Burnup Engine: límites analíticos y comportamiento físico.
"""
from __future__ import annotations

import math
from pathlib import Path

from app.main import DATA_DIR, app
from app.application.production_service import ProductionService
from app.domain.burnup_calculator import BurnupCalculator
from app.infrastructure.repositories.local_reaction_data import LocalReactionDataProvider
from app.infrastructure.stopping.factory import build_stopping_provider
from fastapi.testclient import TestClient

client = TestClient(app)
service = ProductionService(
    stopping=build_stopping_provider(DATA_DIR / "stopping"),
    rxn=LocalReactionDataProvider(DATA_DIR),
)
calc = BurnupCalculator()
LAMBDA_F18 = math.log(2) / (109.77 * 60.0)


def test_limite_sin_quemado():
    """k=0 reproduce exactamente el modelo estándar A_sat*I*(1-e^{-λt})."""
    a_sat, i, t_min = 9336.8, 37.0, 60.0
    got = calc.eob_with_burnup(a_sat, i, t_min, LAMBDA_F18, 0.0)
    esperado = a_sat * i * (1.0 - math.exp(-LAMBDA_F18 * t_min * 60.0))
    assert math.isclose(got, esperado, rel_tol=1e-12)


def test_caso_limite_lambda_igual_k():
    """λ=k no diverge (forma límite)."""
    got = calc.eob_with_burnup(1000.0, 1.0, 60.0, 1e-3, 1e-3)
    esperado = 1000.0 * 1e-3 * 3600.0 * math.exp(-1e-3 * 3600.0)
    assert math.isclose(got, esperado, rel_tol=1e-9)


def test_quemado_tipico_despeciable_en_un_lote():
    """Ciclotrón médico típico: pérdida global por quemado < 0.5%."""
    r = service.burnup_compare(
        reaction_id="o18_p_n_f18", target_id="h2_18o",
        beam_energy_mev=16.5, current_ua=37.0, irradiation_time_min=60.0,
        beam_spot_cm2=1.0, burnup_xs_mb=500.0)
    assert r["loss_percent"] < 0.5
    assert r["eob_no_burnup_gbq"] > r["eob_with_burnup_gbq"]


def test_perdida_crece_con_sigma_quemado():
    r1 = service.burnup_compare("o18_p_n_f18", "h2_18o", 16.5, 37.0, 60.0, 1.0, 500.0)
    r2 = service.burnup_compare("o18_p_n_f18", "h2_18o", 16.5, 37.0, 60.0, 1.0, 5000.0)
    assert r2["loss_percent"] > r1["loss_percent"]


def test_api_burnup():
    r = client.post("/api/v1/production/burnup", json={
        "reaction_id": "o18_p_n_f18", "target_id": "h2_18o",
        "beam_energy_mev": 16.5, "current_ua": 37.0,
        "irradiation_time_min": 60.0, "beam_spot_cm2": 1.0, "burnup_xs_mb": 500.0})
    assert r.status_code == 200
    body = r.json()
    assert body["model"].startswith("single-group")
    assert body["loss_percent"] < 0.5
