"""Tests de enfriamiento con fuente citada y perfiles versionados (fase 13).

Reglas bajo prueba: h/geometría solo con fuente citada (nunca inventadas);
registros versionados que nunca sobrescriben; irradiación por perfil+
versión reproducible; FEM térmico usa la h registrada vigente — sin
configuración 404 no_demostrable, sin runtime 503 honesto.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.production_service import ProductionService
from app.domain.cyclotron import CiclotronRegistry
from app.domain.irradiation_profile import PerfilIrradiacionRegistry
from app.domain.target_cooling import CoolingInvalido, CoolingRegistry
from app.infrastructure.repositories.factory import build_reaction_provider
from app.infrastructure.stopping.factory import build_stopping_provider
from app.infrastructure.stopping.pstar_stopping import PstarTables
from app.main import DATA_DIR
from app.presentation.routers import cyclotron_api, irradiation_api

PSTAR_DIR = DATA_DIR / "stopping" / "pstar"


# ------------------------------------------------- dominio: enfriamiento
def test_cooling_exige_fuente_citada():
    reg = CoolingRegistry()
    with pytest.raises(CoolingInvalido, match="fuente"):
        reg.registrar("h2_18o", 1.2, "spiral groove backing", " ", "calidad")


def test_cooling_h_fuera_de_rango_fisico():
    reg = CoolingRegistry()
    with pytest.raises(CoolingInvalido, match="rango físico"):
        reg.registrar("h2_18o", 500.0, "geo", "fuente x", "calidad")


def test_cooling_versionado_nunca_sobrescribe():
    reg = CoolingRegistry()
    v1 = reg.registrar("h2_18o", 1.2, "backplate estriado espiral",
                       "ficha técnica proveedor X (citada)", "calidad")
    v2 = reg.registrar("h2_18o", 2.0, "backplate estriado espiral mejorado",
                       "medición interna validada, doc. INT-2026-04",
                       "calidad", motivo_version="nueva medición de h")
    assert (v1.version, v2.version) == (1, 2)
    assert reg.vigente("h2_18o").h_w_cm2_k == 2.0
    assert reg.version("h2_18o", 1).h_w_cm2_k == 1.2   # historial intacto
    with pytest.raises(CoolingInvalido, match="no_demostrable"):
        reg.vigente("blanco_sin_config")


# ------------------------------------------------------------- API fixture
@pytest.fixture(scope="module")
def client():
    service = ProductionService(
        stopping=build_stopping_provider(DATA_DIR / "stopping"),
        rxn=build_reaction_provider(DATA_DIR))
    cic = CiclotronRegistry()
    pstar = PstarTables(PSTAR_DIR)
    cooling = CoolingRegistry()
    perfiles = PerfilIrradiacionRegistry()
    cyclotron_api.init(service, registry=cic, pstar=pstar)
    irradiation_api.init(service, cic, cooling, perfiles, pstar=pstar)
    app = FastAPI()
    app.include_router(cyclotron_api.router)
    app.include_router(irradiation_api.router)
    c = TestClient(app)
    r = c.post("/api/v1/cyclotrons", json={
        "fabricante": "IBA", "modelo": "KIUBE", "energia_max_mev": 18.0,
        "corriente_max_ua": 300.0, "estado_operativo": "proyectado",
        "fuente": "spec pública del fabricante aportada por el usuario",
        "registrado_por": "calidad"})
    assert r.status_code == 201, r.text
    c._kiube_id = r.json()["ciclotron_id"]
    return c


PERFIL_BASE = dict(nombre="f18_kiube_2h", reaccion_id="o18_p_n_f18",
                   blanco_id="h2_18o", energia_mev=18.0, corriente_ua=300.0,
                   tiempo_min=120.0,
                   ventana={"material": "iron", "espesor_g_cm2": 0.02075,
                            "descripcion": "Havar 25 µm ≈ Fe (declarado)"},
                   haz={"forma": "gaussiano", "sigma_cm": 0.5,
                        "notas": "perfil supuesto, sin medición de haz"},
                   registrado_por="calidad")


def test_perfil_versionado_e_irradiacion_por_version(client):
    r = client.post("/api/v1/irradiation-profiles", json=PERFIL_BASE)
    assert r.status_code == 201, r.text
    pid = r.json()["perfil_id"]
    r = client.post("/api/v1/irradiation-profiles", json={
        **PERFIL_BASE, "tiempo_min": 90.0,
        "motivo_version": "corrida corta para prueba de sprint"})
    assert r.json()["version"] == 2
    assert len(client.get(
        f"/api/v1/irradiation-profiles/{pid}/versions").json()) == 2

    # irradiar con la versión 1 (120 min) explícita — reproducible
    r = client.post(
        f"/api/v1/cyclotrons/{client._kiube_id}/irradiations/by-profile",
        json={"perfil_id": pid, "version": 1})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["perfil_version"] == 1 and d["tiempo_min"] == 120.0
    assert d["ventana"]["energia_en_blanco_mev"] < 18.0
    assert d["eob"]["eob_activity_gbq"] > 0

    # vigente (v2, 90 min) → factor de saturación menor → menos EOB
    r2 = client.post(
        f"/api/v1/cyclotrons/{client._kiube_id}/irradiations/by-profile",
        json={"perfil_id": pid})
    d2 = r2.json()
    assert d2["perfil_version"] == 2 and d2["tiempo_min"] == 90.0
    assert d2["eob"]["eob_activity_gbq"] < d["eob"]["eob_activity_gbq"]


def test_perfil_que_supera_la_maquina_es_422(client):
    r = client.post("/api/v1/irradiation-profiles", json={
        **PERFIL_BASE, "nombre": "imposible", "energia_mev": 19.0})
    pid = r.json()["perfil_id"]
    r = client.post(
        f"/api/v1/cyclotrons/{client._kiube_id}/irradiations/by-profile",
        json={"perfil_id": pid})
    assert r.status_code == 422
    assert "18.0 MeV" in r.json()["detail"]


def test_thermal_sin_cooling_registrado_es_404(client):
    r = client.post("/api/v1/targets/blanco_x/thermal", json={
        "energia_mev": 18.0, "corriente_ua": 300.0})
    assert r.status_code == 404
    assert "no_demostrable" in r.json()["detail"]


def test_thermal_con_h_registrada_usa_vigente(client):
    r = client.post("/api/v1/targets/h2_18o/cooling-configs", json={
        "h_w_cm2_k": 1.2, "geometria": "backplate estriado espiral",
        "fuente": "literatura especializada citada por el usuario",
        "registrado_por": "calidad"})
    assert r.status_code == 201, r.text
    # sin runtime Elmer en este entorno → 503 honesto (nunca estimado);
    # con runtime, la respuesta citaría config_id/versión/fuente
    r = client.post("/api/v1/targets/h2_18o/thermal", json={
        "energia_mev": 18.0, "corriente_ua": 300.0})
    assert r.status_code == 503
    assert "no demostrable" in r.json()["detail"] or "ElmerSolver" in r.json()["detail"]
