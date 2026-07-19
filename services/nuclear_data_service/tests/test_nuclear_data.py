"""
Tests del Nuclear Data Service (MVP: 18O(p,n)18F + decaimiento 18F).
"""
from __future__ import annotations

import math
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app, DATA_DIR
from app.infrastructure.repositories.csv_cross_section_repository import CsvCrossSectionRepository
from app.infrastructure.repositories.json_decay_repository import JsonDecayRepository

client = TestClient(app)


def test_cross_section_repository_carga_dataset_iaea():
    repo = CsvCrossSectionRepository(DATA_DIR)
    rxn = repo.get_reaction("o18_p_n_f18")
    assert rxn is not None
    assert rxn.notation == "18O(p,n)18F"
    assert rxn.threshold_mev == 2.574
    assert len(rxn.points) == 100           # dataset IAEA May-2021 completo
    assert rxn.points[0].energy_mev == 2.55
    assert rxn.points[-1].energy_mev == 30.0
    pico = max(p.sigma_mb for p in rxn.points)
    assert 500.0 < pico < 560.0             # pico Padé ~533 mb


def test_decay_repository_f18():
    repo = JsonDecayRepository(DATA_DIR)
    d = repo.get_decay("18F")
    assert d is not None
    # T1/2 = 109.77 min (DDEP/LiveChart)
    assert abs(d.half_life_s - 109.77 * 60) < 1.0
    # lambda = ln2 / T1/2
    assert math.isclose(d.decay_constant_s, math.log(2) / (109.77 * 60), rel_tol=1e-9)
    # ramas beta+ + EC = 1
    total = sum(m.branching_ratio for m in d.decay_modes)
    assert math.isclose(total, 1.0, abs_tol=1e-3)


def test_api_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_api_reactions():
    r = client.get("/api/v1/reactions")
    assert r.status_code == 200
    data = {x["reaction_id"]: x for x in r.json()}
    assert data["o18_p_n_f18"]["n_points"] == 100
    assert data["n14_p_a_c11"]["n_points"] == 76


def test_api_cross_section_window():
    r = client.get("/api/v1/reactions/o18_p_n_f18/cross-section?e_min=5&e_max=6")
    assert r.status_code == 200
    pts = r.json()["points"]
    assert all(5.0 <= p["energy_mev"] <= 6.0 for p in pts)


def test_api_decay():
    r = client.get("/api/v1/nuclides/18F/decay")
    assert r.status_code == 200
    assert abs(r.json()["half_life_s"] - 6586.2) < 1.0


def test_reaction_11c_catalogada():
    repo = CsvCrossSectionRepository(DATA_DIR)
    rxn = repo.get_reaction("n14_p_a_c11")
    assert rxn is not None
    assert rxn.notation == "14N(p,alpha)11C"
    assert rxn.threshold_mev == 3.132
    assert len(rxn.points) == 76
    pico = max(pt.sigma_mb for pt in rxn.points)
    assert 240.0 < pico < 260.0             # resonancia ~249 mb @ 7.5 MeV


def test_decay_11c():
    repo = JsonDecayRepository(DATA_DIR)
    d = repo.get_decay("11C")
    assert d is not None
    # T1/2 = 20.364 min (DDEP/LiveChart)
    assert abs(d.half_life_s - 20.364 * 60) < 0.5
    assert math.isclose(d.decay_constant_s, math.log(2) / (20.364 * 60), rel_tol=1e-9)


def test_api_reactions_catalogo_completo():
    r = client.get("/api/v1/reactions")
    ids = {x["reaction_id"] for x in r.json()}
    assert ids == {"o18_p_n_f18", "n14_p_a_c11", "n15_p_n_o15", "zn68_p_n_ga68"}


def test_reactions_15o_68ga_catalogadas():
    repo = CsvCrossSectionRepository(DATA_DIR)
    o15 = repo.get_reaction("n15_p_n_o15")
    ga68 = repo.get_reaction("zn68_p_n_ga68")
    assert o15 is not None and len(o15.points) == 388 and o15.threshold_mev == 3.77
    assert ga68 is not None and len(ga68.points) == 60 and ga68.threshold_mev == 3.76
    assert 800.0 < max(p.sigma_mb for p in ga68.points) < 900.0   # pico ~877 mb


def test_decay_15o_y_68ga():
    repo = JsonDecayRepository(DATA_DIR)
    o15 = repo.get_decay("15O")
    ga68 = repo.get_decay("68Ga")
    assert o15 is not None and abs(o15.half_life_s - 122.24) < 0.01
    assert ga68 is not None and abs(ga68.half_life_s - 67.71 * 60) < 1.0
    total = sum(m.branching_ratio for m in ga68.decay_modes)
    assert math.isclose(total, 1.0, abs_tol=1e-3)


def test_api_datasets_provenance():
    r = client.get("/api/v1/datasets")
    assert r.status_code == 200
    ids = [d["id"] for d in r.json()]
    assert "o18_p_n_f18_iaea2021" in ids
    assert "n14_p_a_c11_iaea2021" in ids
    assert "c11_decay_ddep" in ids
