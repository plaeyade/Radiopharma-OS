"""Tests del dominio del ciclotrón (Informe §1558; EDS 5.9).

Reglas bajo prueba: specs solo con fuente citada; registro versionado que
nunca sobrescribe; irradiaciones validadas contra límites reales de la
máquina; SRIM honestamente no_configurado (nunca simulado).
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.production_service import ProductionService
from app.domain.cyclotron import CiclotronInvalido, CiclotronRegistry
from app.infrastructure.repositories.factory import build_reaction_provider
from app.infrastructure.stopping.factory import build_stopping_provider
from app.presentation.routers import cyclotron_api

from app.main import DATA_DIR


def _registry() -> CiclotronRegistry:
    return CiclotronRegistry()


def _kiube_kwargs(**kw):
    base = dict(fabricante="IBA", modelo="KIUBE",
                energia_max_mev=18.0, corriente_max_ua=300.0,
                estado_operativo="proyectado",
                fuente="spec pública del fabricante aportada por el usuario",
                registrado_por="calidad")
    base.update(kw)
    return base


# ---------------------------------------------------------------- dominio
def test_registro_exige_fuente_citada():
    reg = _registry()
    with pytest.raises(CiclotronInvalido, match="fuente"):
        reg.registrar(**_kiube_kwargs(fuente=" "))


def test_registro_versionado_nunca_sobrescribe():
    reg = _registry()
    v1 = reg.registrar(**_kiube_kwargs())
    v2 = reg.registrar(**_kiube_kwargs(
        corriente_max_ua=350.0, motivo_version="upgrade de fuente de iones"))
    assert v1.ciclotron_id == v2.ciclotron_id
    assert (v1.version, v2.version) == (1, 2)
    assert reg.obtener(v1.ciclotron_id).corriente_max_ua == 350.0   # vigente
    assert reg.obtener(v1.ciclotron_id, version=1).corriente_max_ua == 300.0
    assert len(reg.versiones(v1.ciclotron_id)) == 2                 # nada borrado


def test_nueva_version_exige_motivo():
    reg = _registry()
    reg.registrar(**_kiube_kwargs())
    with pytest.raises(CiclotronInvalido, match="motivo"):
        reg.registrar(**_kiube_kwargs(corriente_max_ua=320.0,
                                      motivo_version=" "))


def test_irradiacion_dentro_de_limites():
    reg = _registry()
    c = reg.registrar(**_kiube_kwargs())
    irr = reg.registrar_irradiacion(c.ciclotron_id, 18.0, 300.0, 120.0,
                                    "o18_p_n_f18", "h2_18o")
    assert irr.ciclotron_version == 1
    assert len(reg.irradiaciones(c.ciclotron_id)) == 1


def test_irradiacion_rechazada_si_supera_maquina():
    reg = _registry()
    c = reg.registrar(**_kiube_kwargs())
    with pytest.raises(CiclotronInvalido, match="18.0 MeV"):
        reg.registrar_irradiacion(c.ciclotron_id, 19.0, 100.0, 60.0,
                                  "o18_p_n_f18", "h2_18o")
    with pytest.raises(CiclotronInvalido, match="300.0 µA"):
        reg.registrar_irradiacion(c.ciclotron_id, 18.0, 350.0, 60.0,
                                  "o18_p_n_f18", "h2_18o")
    # lo rechazado NO queda registrado
    assert reg.irradiaciones(c.ciclotron_id) == []


def test_fuera_de_servicio_no_irradia():
    reg = _registry()
    c = reg.registrar(**_kiube_kwargs(estado_operativo="fuera_de_servicio"))
    with pytest.raises(CiclotronInvalido, match="fuera_de_servicio"):
        reg.registrar_irradiacion(c.ciclotron_id, 18.0, 100.0, 60.0,
                                  "o18_p_n_f18", "h2_18o")


# ------------------------------------------------------------------- API
@pytest.fixture(scope="module")
def client():
    service = ProductionService(
        stopping=build_stopping_provider(DATA_DIR / "stopping"),
        rxn=build_reaction_provider(DATA_DIR))
    cyclotron_api.init(service, CiclotronRegistry())
    app = FastAPI()
    app.include_router(cyclotron_api.router)
    return TestClient(app)


def test_api_corrida_tipo_kiube(client):
    r = client.post("/api/v1/cyclotrons", json=_kiube_kwargs())
    assert r.status_code == 201, r.text
    cid = r.json()["ciclotron_id"]

    r = client.post(f"/api/v1/cyclotrons/{cid}/irradiations", json={
        "energia_mev": 18.0, "corriente_ua": 300.0, "tiempo_min": 120.0})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["potencia_haz_w"] == 5400.0           # 18 MeV × 300 µA
    assert "cota superior" in d["nota_honestidad"]  # degradación no aplicada
    eob = d["eob"]
    assert eob["eob_activity_gbq"] > 0
    assert eob["dataset_id"]                        # σ(E) con fuente real

    r = client.get(f"/api/v1/cyclotrons/{cid}/irradiations")
    assert len(r.json()) == 1


def test_api_rechaza_corrida_imposible(client):
    r = client.post("/api/v1/cyclotrons", json=_kiube_kwargs())
    cid = r.json()["ciclotron_id"]
    r = client.post(f"/api/v1/cyclotrons/{cid}/irradiations", json={
        "energia_mev": 18.0, "corriente_ua": 400.0, "tiempo_min": 30.0})
    assert r.status_code == 422
    assert "300.0 µA" in r.json()["detail"]


def test_api_stopping_power_honesto(client):
    r = client.get("/api/v1/stopping-power/status")
    d = r.json()
    assert d["proveedor_configurado"]["fuente"]     # proveedor real citado
    assert d["srim"]["estado"] == "no_configurado"  # jamás simulado
