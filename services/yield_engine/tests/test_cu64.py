"""Fase 22 — producción de ⁶⁴Cu por ⁶⁴Ni(p,n)⁶⁴Cu.

Dataset IAEA-NDS verificado (46 puntos, 2,6–25 MeV, pico 665,5 mb a
10,5 MeV), λ real de ⁶⁴Cu (T½ = 12,7004 h, NuDat/ICRP-107) y stopping
del blanco Ni-64 por proxy PSTAR cobre DECLARADO (PSTAR no publica Ni).
Sin canal competidor registrado → impureza no_demostrable, nunca
estimada.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app, service

client = TestClient(app)


def _eob(energia: float) -> dict:
    r = client.post("/api/v1/production", json={
        "reaction_id": "ni64_p_n_cu64", "target_id": "ni64",
        "beam_energy_mev": energia, "current_ua": 50.0,
        "irradiation_time_min": 60.0})
    assert r.status_code == 200, r.text
    return r.json()


def test_lambda_cu64_real():
    """λ(⁶⁴Cu) = ln2/(12,7004 h) — biblioteca nuclear, nunca asumida."""
    import math
    assert service.decay_constant_s("64Cu") == pytest.approx(
        math.log(2) / (12.7004 * 3600), rel=1e-9)


def test_eob_cu64_positivo_con_dataset_verificado():
    d = _eob(12.0)
    assert d["eob_activity_gbq"] > 0
    assert d["dataset_id"] == "ni64_p_n_cu64_iaea"
    assert "PSTAR" in d["stopping_source"] or "ATIMA" in d["stopping_source"]


def test_eob_cu64_monotono_con_energia():
    """Blanco grueso: más energía de entrada → más rendimiento (σ>0 en
    todo el rango adicional)."""
    assert _eob(18.0)["eob_activity_gbq"] > _eob(6.0)["eob_activity_gbq"]


def test_irradiacion_cu64_impureza_no_demostrable():
    """Sin canal competidor con dataset citado → la irradiación declara
    impureza no_demostrable (nunca estimada, 49.11)."""
    r = client.post("/api/v1/cyclotrons", json={
        "nombre": "KIUBE-Cu64-test", "fabricante": "IBA", "modelo": "KIUBE",
        "energia_max_mev": 18.0, "energias_mev": [18.0],
        "corriente_max_ua": 150.0,
        "fuente": "ficha técnica IBA KIUBE citada por el usuario",
        "registrado_por": "tester"})
    assert r.status_code == 201, r.text
    cid = r.json()["ciclotron_id"]
    r = client.post(f"/api/v1/cyclotrons/{cid}/irradiations", json={
        "reaccion_id": "ni64_p_n_cu64", "blanco_id": "ni64",
        "energia_mev": 18.0, "corriente_ua": 50.0,
        "tiempo_min": 60.0, "registrado_por": "tester"})
    assert r.status_code in (200, 201), r.text
    imp = r.json()["impurezas"]
    assert isinstance(imp, dict) and imp.get("no_demostrable") is True
    assert "motivo" in imp


def test_stopping_proxy_cu_declarado_en_fuente():
    """El blanco Ni-64 declara honestamente su proxy de stopping."""
    from app.application.target_catalog import TARGET_CATALOG
    t = TARGET_CATALOG["ni64"]
    assert t.stopping_material == "ni64"
    assert "proxy" in t.label.lower()
    fuente = service.stopping_status()["fuente"]
    assert "PSTAR" in fuente
