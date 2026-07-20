"""
Tests del SPC del QC Engine (carta Shewhart I + reglas WE/Nelson + Cpk):
exactitud estadística, detección de cada regla y API.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain.spc import shewhart_spc
from app.main import app

client = TestClient(app)

BASE = [7.10, 7.20, 6.95, 7.05, 7.15, 7.00, 7.10, 6.90, 7.05, 7.15]


# --- exactitud de límites -----------------------------------------------------

def test_limites_exactos():
    r = shewhart_spc(BASE)
    mean = sum(BASE) / len(BASE)
    sigma = (sum((v - mean) ** 2 for v in BASE) / (len(BASE) - 1)) ** 0.5
    assert r.mean == pytest.approx(mean)
    assert r.sigma == pytest.approx(sigma)
    assert r.ucl == pytest.approx(mean + 3 * sigma)
    assert r.lcl == pytest.approx(mean - 3 * sigma)
    assert r.in_control
    assert all(not p.violations for p in r.points)


def test_proceso_estable_en_control():
    r = shewhart_spc([10.0, 10.1, 9.9, 10.05, 9.95, 10.0, 10.02, 9.98])
    assert r.in_control


# --- reglas WE/Nelson -----------------------------------------------------------

def test_we1_punto_fuera_de_3sigma():
    vals = BASE + [10.5]
    r = shewhart_spc(vals)
    assert "WE1" in r.points[-1].violations
    assert not r.in_control


def test_we2_dos_de_tres_fuera_de_2sigma():
    # serie larga estable (σ ≈ 0.05) + 2 puntos entre 2σ y 3σ finales
    base = [6.95, 7.05] * 15
    r = shewhart_spc(base + [7.14, 7.14])
    assert any("WE2" in p.violations for p in r.points[-2:])
    assert all("WE1" not in p.violations for p in r.points)  # sin WE1


def test_we3_cuatro_de_cinco_fuera_de_1sigma():
    # 4 de 5 consecutivos entre 1σ y 2σ finales, mismo lado
    base = [6.95, 7.05] * 15
    r = shewhart_spc(base + [7.10] * 4)
    assert any("WE3" in p.violations for p in r.points[-4:])
    assert all("WE2" not in p.violations for p in r.points)  # sin WE2


def test_we4_ocho_mismo_lado():
    mean = sum(BASE) / len(BASE)
    vals = BASE + [mean + 0.01] * 8
    r = shewhart_spc(vals)
    assert "WE4" in r.points[-1].violations
    assert not r.in_control


def test_trend_seis_consecutivos():
    vals = BASE + [7.2, 7.3, 7.4, 7.5, 7.6, 7.7]
    r = shewhart_spc(vals)
    assert "TREND" in r.points[-1].violations


# --- capacidad de proceso -------------------------------------------------------

def test_cpk_exacto():
    r = shewhart_spc(BASE, spec_low=6.5, spec_high=7.5)
    assert r.cp == pytest.approx((7.5 - 6.5) / (6 * r.sigma))
    assert r.cpk == pytest.approx(
        min((7.5 - r.mean) / (3 * r.sigma),
            (r.mean - 6.5) / (3 * r.sigma)))
    assert r.cpk > 1.0  # proceso capaz con estos datos


def test_cpk_unilateral():
    r = shewhart_spc([0.97, 0.96, 0.98, 0.975, 0.965], spec_low=0.95)
    assert r.cp is None
    assert r.cpk == pytest.approx((r.mean - 0.95) / (3 * r.sigma))


def test_sin_specs_sin_capacidad():
    r = shewhart_spc(BASE)
    assert r.cp is None and r.cpk is None


# --- validaciones -----------------------------------------------------------------

def test_validaciones():
    with pytest.raises(ValueError):
        shewhart_spc([1.0])                       # un solo punto
    with pytest.raises(ValueError):
        shewhart_spc([1.0, float("nan")])         # no finito
    with pytest.raises(ValueError):
        shewhart_spc(BASE, spec_low=8.0, spec_high=7.0)  # specs invertidos


def test_sigma_cero_no_explota():
    r = shewhart_spc([5.0] * 10)
    assert r.sigma == 0.0 and r.ucl == r.lcl == 5.0
    assert all(not p.violations for p in r.points)


def test_labels():
    labels = [f"L{i + 1}" for i in range(len(BASE))]
    r = shewhart_spc(BASE, labels=labels)
    assert r.points[0].label == "L1"
    assert r.points[-1].label == f"L{len(BASE)}"


# --- API ---------------------------------------------------------------------------

def test_api_spc_en_control():
    resp = client.post("/api/v1/qc/spc",
                       json={"values": BASE, "spec_low": 6.5, "spec_high": 7.5})
    assert resp.status_code == 200
    d = resp.json()
    assert d["in_control"] and d["n"] == len(BASE)
    assert d["cpk"] > 1.0
    assert "25.17" in d["note"]


def test_api_spc_detecta_violacion():
    resp = client.post("/api/v1/qc/spc", json={"values": BASE + [10.5]})
    assert resp.status_code == 200
    d = resp.json()
    assert not d["in_control"]
    assert "WE1" in d["points"][-1]["violations"]


def test_api_spc_validacion():
    assert client.post("/api/v1/qc/spc", json={"values": [1.0]}).status_code == 422
    assert client.post("/api/v1/qc/spc", json={"values": []}).status_code == 422
