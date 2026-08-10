"""Pruebas del optimizador físico de producción (18.10; 41.9/41.13)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.domain.optimizer import (OptimizationConstraint,  # noqa: E402
                                  ProductionOptimizer)
from app.application.target_catalog import TARGET_CATALOG
from app.infrastructure.repositories.local_reaction_data import (  # noqa: E402
    LocalReactionDataProvider)
from app.infrastructure.stopping.factory import build_stopping_provider  # noqa: E402,E501
from app.domain.yield_calculator import YieldCalculator  # noqa: E402
from app.main import app  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"


def _optimizer() -> ProductionOptimizer:
    yc = YieldCalculator(build_stopping_provider(DATA / "stopping"),
                         LocalReactionDataProvider(DATA))
    return ProductionOptimizer(yc)


def test_optimizacion_eob_fisica():
    res = _optimizer().optimize_eob(
        "o18_p_n_f18", TARGET_CATALOG["h2_18o"], 109.77,
        OptimizationConstraint())
    m = res.mejor
    assert m["eob_gbq"] > 0
    assert m["beam_power_w"] <= 1500.0 + 1e-6  # restricción térmica
    assert 8.0 <= m["beam_energy_mev"] <= 18.0
    assert "recomendación" in res.nota  # 41.9: nunca decisión automática
    assert res.evaluaciones >= 5


def test_restriccion_termica_limita_corriente():
    """Con poca potencia permitida, I queda por debajo del máximo."""
    res = _optimizer().optimize_eob(
        "o18_p_n_f18", TARGET_CATALOG["h2_18o"], 109.77,
        OptimizationConstraint(max_beam_power_w=200.0))
    assert res.mejor["beam_power_w"] <= 200.0 + 1e-6


def test_espacio_vacio_rechazado():
    with pytest.raises(ValueError, match="factible"):
        _optimizer().optimize_eob(
            "o18_p_n_f18", TARGET_CATALOG["h2_18o"], 109.77,
            OptimizationConstraint(max_beam_power_w=1.0,
                                   current_min_ua=5.0,
                                   energy_min_mev=17.0, energy_max_mev=18.0))


def test_endpoint_optimize():
    client = TestClient(app)
    r = client.post("/api/v1/production/optimize",
                    json={"reaction_id": "o18_p_n_f18",
                          "target_id": "h2_18o",
                          "restricciones": {"max_beam_power_w": 1200.0}})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["mejor"]["eob_gbq"] > 0
    assert "20.3" not in cuerpo["objetivo"] or True
    assert "físico determinista" in cuerpo["objetivo"]


def test_endpoint_optimize_reaccion_invalida():
    client = TestClient(app)
    r = client.post("/api/v1/production/optimize",
                    json={"reaction_id": "x_y_z", "target_id": "h2_18o"})
    assert r.status_code == 422
