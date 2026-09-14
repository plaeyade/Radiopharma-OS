"""Tests de la degradación en ventana con PSTAR/NIST (19.10, fase 12).

Reglas bajo prueba: la energía de salida se calcula SOLO con rangos CSDA
de las tablas NIST versionadas; un haz detenido en la ventana se declara
error — jamás se inventa una energía de salida; sin tablas configuradas
el endpoint responde 503 honesto.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.production_service import ProductionService
from app.domain.cyclotron import CiclotronRegistry
from app.infrastructure.repositories.factory import build_reaction_provider
from app.infrastructure.stopping.factory import build_stopping_provider
from app.infrastructure.stopping.pstar_stopping import (PstarTables,
                                                        VentanaInvalida)
from app.main import DATA_DIR
from app.presentation.routers import cyclotron_api

PSTAR_DIR = DATA_DIR / "stopping" / "pstar"


# ------------------------------------------------------------- tablas PSTAR
def test_tablas_pstar_tienen_fuente_y_datos_reales():
    tablas = PstarTables(PSTAR_DIR)
    assert set(tablas.materiales()) == {"water", "iron", "copper"}
    # valores NIST conocidos de las propias tablas versionadas
    s = tablas.stopping_power("water", 16.0)
    assert 25.0 < s < 35.0         # MeV·cm²/g — valor NIST a 16 MeV ≈ 31
    r = tablas.range_g_cm2("water", 16.0)
    assert 0.20 < r < 0.35         # rango CSDA NIST ≈ 0,28 g/cm² (≈2,8 mm)
    assert "PSTAR" in tablas.source_label()


def test_degradacion_monotona_y_consistente_con_rango():
    tablas = PstarTables(PSTAR_DIR)
    e_out = tablas.degradar("iron", 0.02, 18.0)
    assert 0 < e_out < 18.0
    # consistencia: R(E_in) − R(E_out) = espesor
    r_in = tablas.range_g_cm2("iron", 18.0)
    r_out = tablas.range_g_cm2("iron", e_out)
    assert abs((r_in - r_out) - 0.02) < 1e-3
    # más espesor → más degradación
    assert tablas.degradar("iron", 0.05, 18.0) < e_out
    # espesor cero → misma energía
    assert tablas.degradar("iron", 0.0, 18.0) == 18.0


def test_haz_detenido_en_ventana_es_error_honesto():
    tablas = PstarTables(PSTAR_DIR)
    with pytest.raises(VentanaInvalida, match="detenido"):
        tablas.degradar("iron", 10.0, 18.0)   # 10 g/cm² >> rango en Fe


# ------------------------------------------------------------------- API
def _client(con_pstar=True):
    service = ProductionService(
        stopping=build_stopping_provider(DATA_DIR / "stopping"),
        rxn=build_reaction_provider(DATA_DIR))
    cyclotron_api.init(
        service, CiclotronRegistry(),
        pstar=PstarTables(PSTAR_DIR) if con_pstar else None)
    app = FastAPI()
    app.include_router(cyclotron_api.router)
    return TestClient(app)


def _registrar_kiube(client):
    r = client.post("/api/v1/cyclotrons", json={
        "fabricante": "IBA", "modelo": "KIUBE", "energia_max_mev": 18.0,
        "corriente_max_ua": 300.0, "estado_operativo": "proyectado",
        "fuente": "spec pública del fabricante aportada por el usuario",
        "registrado_por": "calidad"})
    assert r.status_code == 201, r.text
    return r.json()["ciclotron_id"]


def test_corrida_con_ventana_degrada_energia():
    client = _client()
    cid = _registrar_kiube(client)
    r = client.post(f"/api/v1/cyclotrons/{cid}/irradiations", json={
        "energia_mev": 18.0, "corriente_ua": 300.0, "tiempo_min": 120.0,
        "ventana": {"material": "iron", "espesor_g_cm2": 0.02,
                    "descripcion": "Havar 25 µm aproximado como Fe "
                                   "(supuesto declarado del usuario)"}})
    assert r.status_code == 201, r.text
    d = r.json()
    v = d["ventana"]
    assert v["energia_en_blanco_mev"] < 18.0
    assert v["perdida_mev"] > 0
    assert v["supuesto_declarado"] is True
    assert "PSTAR" in v["fuente"]
    # EOB con energía degradada < EOB cota superior sin ventana
    r2 = client.post(f"/api/v1/cyclotrons/{cid}/irradiations", json={
        "energia_mev": 18.0, "corriente_ua": 300.0, "tiempo_min": 120.0})
    assert d["eob"]["eob_activity_gbq"] < r2.json()["eob"]["eob_activity_gbq"]


def test_corrida_ventana_que_detiene_el_haz_es_422():
    client = _client()
    cid = _registrar_kiube(client)
    r = client.post(f"/api/v1/cyclotrons/{cid}/irradiations", json={
        "energia_mev": 18.0, "corriente_ua": 300.0, "tiempo_min": 60.0,
        "ventana": {"material": "iron", "espesor_g_cm2": 50.0}})
    assert r.status_code == 422
    assert "detenido" in r.json()["detail"]


def test_ventana_sin_pstar_es_503_honesto():
    client = _client(con_pstar=False)
    cid = _registrar_kiube(client)
    r = client.post(f"/api/v1/cyclotrons/{cid}/irradiations", json={
        "energia_mev": 18.0, "corriente_ua": 300.0, "tiempo_min": 60.0,
        "ventana": {"material": "iron", "espesor_g_cm2": 0.02}})
    assert r.status_code == 503
    assert "no demostrable" in r.json()["detail"]


def test_status_reporta_pstar_configurado():
    client = _client()
    d = client.get("/api/v1/stopping-power/status").json()
    assert d["pstar_ventanas"]["estado"] == "configurado"
    assert d["pstar_ventanas"]["materiales"] == ["copper", "iron", "water"]
    assert d["srim"]["estado"] == "no_configurado"
