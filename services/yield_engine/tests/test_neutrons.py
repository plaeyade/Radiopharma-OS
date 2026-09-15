"""Fase 23 — neutrones rápidos/térmicos de la irradiación.

Fuente: TALYS-2 real (espectros (p,xn) cacheados como datos versionados,
fuente citada). Termalización: SOLO transporte MC real (OpenGATE/Geant4
FTFP_BERT_HP + G4NDL). Honestidad 19.24: sin runtime → 503 sin_runtime;
sin G4NDL → tally no_demostrable; los térmicos jamás se estiman
analíticamente.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.gate.neutron_tally import (
    NeutronTallyRunner, TallyGateUnavailable, bandas_desde_espectro_fuente)
from app.infrastructure.talys_spectra import (TalysError, TalysSpectraRunner,
                                              parse_nspec)
from app.main import app, _neutron_service

client = TestClient(app)
FIXTURE = Path(__file__).parent / "fixtures" / "nspec0018.000.tot"


def test_parse_nspec_real_talys():
    """Fixture = salida REAL de TALYS-2.23 (Ni-64 p 18 MeV, 159 bines)."""
    d = parse_nspec(FIXTURE.read_text())
    assert len(d["puntos"]) == 159
    assert d["sigma_total_mb"] > 0
    comp = d["componentes_mb"]
    assert set(comp) == {"directo", "preequilibrio", "compound"}
    assert comp["preequilibrio"] > 0 and comp["compound"] > 0
    # La suma de componentes ≈ total (integración trapezoidal real)
    assert abs(sum(comp.values()) - d["sigma_total_mb"]) < 1.0


def test_parse_nspec_sin_datos_es_error_honesto():
    with pytest.raises(TalysError):
        parse_nspec("# header vacío\n# sin puntos numéricos\n")


def test_bandas_fuente_termicos_cero_declarado():
    """TALYS emite desde 1 keV: térmicos fuente = 0 DECLARADO, la
    termalización es exclusiva del tally MC (nunca estimada)."""
    d = parse_nspec(FIXTURE.read_text())
    b = bandas_desde_espectro_fuente(d["puntos"])
    assert b["termicos_mb"] == 0.0
    assert b["rapidos_mb"] > 0
    assert b["total_mb"] == pytest.approx(d["sigma_total_mb"], rel=1e-6)


def test_status_honesto_de_runtimes():
    r = client.get("/api/v1/neutrons/status")
    assert r.status_code == 200
    d = r.json()
    assert "disponible" in d["talys"] and "disponible" in d["opengate"]


def test_produccion_503_sin_runtime_talys(monkeypatch, tmp_path):
    """Sin TALYS real → 503 sin_runtime; nunca se simula el espectro."""
    monkeypatch.setattr(_neutron_service._spectra, "_cmd", "/no/existe/talys")
    monkeypatch.setattr(_neutron_service._spectra, "_cache", tmp_path)
    r = client.post("/api/v1/neutrons/production", json={
        "reaccion_id": "ni64_p_n_cu64", "blanco_id": "ni64",
        "energia_mev": 18.0, "corriente_ua": 50.0})
    assert r.status_code == 503
    assert "sin_runtime" in r.text or "TALYS" in r.text


def test_produccion_422_bajo_umbral():
    r = client.post("/api/v1/neutrons/production", json={
        "reaccion_id": "ni64_p_n_cu64", "blanco_id": "ni64",
        "energia_mev": 2.0, "corriente_ua": 50.0})
    assert r.status_code == 422


def test_tally_503_sin_opengate():
    """Sin OpenGATE/G4NDL → 503: térmicos no_demostrable, nunca estimados."""
    runner = NeutronTallyRunner(python_cmd="/no/existe")
    assert not runner.check()
    with pytest.raises(TallyGateUnavailable):
        runner.run(Path("/tmp/caso_inexistente_tally"))


@pytest.mark.skipif(
    not os.environ.get("TALYS_CMD") or
    not Path(os.environ.get("TALYS_CMD", "/no")).exists(),
    reason="sin runtime TALYS real — comportamiento honesto ya cubierto")
def test_produccion_real_end_to_end(tmp_path):
    runner = TalysSpectraRunner(tmp_path)
    svc_spectra = _neutron_service._spectra
    _neutron_service._spectra = runner
    try:
        d = _neutron_service.produccion("ni64_p_n_cu64", "ni64", 18.0, 50.0)
    finally:
        _neutron_service._spectra = svc_spectra
    assert d["neutrones_por_proton"] > 0
    assert d["tasa_neutrones_s"] > 0
    assert d["bandas_fuente"]["termicos_mb"] == 0.0
    assert "TALYS" in d["fuente"]


def test_build_case_con_blindajes(tmp_path):
    """Las capas de blindaje entran al case.json real (materiales NIST,
    espesores) — nunca factores de atenuación inventados."""
    from app.infrastructure.gate.neutron_tally import build_case
    import json
    build_case(tmp_path, [[1.0, 100.0], [2.0, 50.0]], 30.0, 100,
               "G4_WATER", 1,
               blindajes=[{"material_g4": "G4_CONCRETE", "espesor_cm": 50.0},
                          {"material_g4": "G4_Pb", "espesor_cm": 5.0}])
    case = json.loads((tmp_path / "case.json").read_text())
    assert len(case["blindajes"]) == 2
    assert case["blindajes"][0]["material_g4"] == "G4_CONCRETE"


def test_tally_api_acepta_blindajes_y_rechaza_extras():
    """Validación estricta (extra=forbid) y límite de espesor."""
    r = client.post("/api/v1/neutrons/transport-tally", json={
        "reaccion_id": "ni64_p_n_cu64", "blanco_id": "ni64",
        "energia_mev": 18.0, "corriente_ua": 50.0,
        "radio_moderador_cm": 30.0, "n_histories": 100,
        "blindajes": [{"material_g4": "G4_CONCRETE", "espesor_cm": 500.0}]})
    assert r.status_code == 422
    r = client.post("/api/v1/neutrons/transport-tally", json={
        "reaccion_id": "ni64_p_n_cu64", "blanco_id": "ni64",
        "energia_mev": 18.0, "corriente_ua": 50.0,
        "radio_moderador_cm": 30.0, "campo_inventado": 1})
    assert r.status_code == 422
