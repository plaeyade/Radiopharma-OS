"""
Resultados de simulación en el Data Lake (EDS 4.9 organización física
`simulation/elmer/`, 7.11 campos de resultados FEM).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.test_jwt_guard import auth_headers


_PAYLOAD = {
    "kind": "elmer_thermal",
    "solver": "ElmerSolver 26.2 (/tmp/sci/bin/ElmerSolver)",
    "reaction_id": "o18_p_n_f18",
    "target_id": "h2_18o",
    "inputs": {"beam_power_w": 720.0, "spot_radius_cm": 0.4,
               "pipeline": "yield→burnup→elmer"},
    "results": {"t_peak_fem_k": 475.79, "t_mean_fem_k": 464.67,
                "heat_flux_max_w_m2": 1.4e7,
                "stresses_mpa": None, "deformations_mm": None},
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


def test_registra_simulacion_y_hash(client):
    r = client.post("/api/v1/simulations", json=_PAYLOAD,
                    headers=auth_headers())
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["simulation_id"].startswith("SIM-")
    assert b["artifact_key"].startswith("simulation/elmer_thermal/")
    assert len(b["record_hash"]) == 64
    assert b["created_by"] == "test.user"
    v = client.get(f"/api/v1/simulations/{b['simulation_id']}/verify",
                   headers=auth_headers())
    assert v.status_code == 200 and v.json()["integrity_ok"]


def test_lista_por_kind_y_reaccion(client):
    client.post("/api/v1/simulations", json=_PAYLOAD, headers=auth_headers())
    r = client.get("/api/v1/simulations",
                   params={"kind": "elmer_thermal",
                           "reaction_id": "o18_p_n_f18"},
                   headers=auth_headers())
    assert r.status_code == 200
    assert any(s["kind"] == "elmer_thermal" for s in r.json())
    r2 = client.get("/api/v1/simulations",
                    params={"kind": "talys_excitation"},
                    headers=auth_headers())
    assert all(s["kind"] == "talys_excitation" for s in r2.json())


def test_get_404_honesto(client):
    r = client.get("/api/v1/simulations/SIM-NOEXISTE", headers=auth_headers())
    assert r.status_code == 404


def test_kind_invalido_422(client):
    r = client.post("/api/v1/simulations",
                    json={**_PAYLOAD, "kind": "inventado"},
                    headers=auth_headers())
    assert r.status_code == 422


def test_results_vacio_rechazado(client):
    r = client.post("/api/v1/simulations",
                    json={**_PAYLOAD, "results": {}}, headers=auth_headers())
    assert r.status_code == 422
    assert "honestidad" in r.json()["detail"]


def test_sin_token_401(client):
    r = client.post("/api/v1/simulations", json=_PAYLOAD)
    assert r.status_code in (401, 403)
