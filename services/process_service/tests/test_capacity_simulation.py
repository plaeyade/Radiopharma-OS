"""Tests del Facility Simulation & Capacity Planning Engine (EDS cap. 37).

Verifica: escenarios aislados y versionados 37.6/37.3, Capacity
Analyzer 37.7 con aritmética exacta, Bottleneck Detector 37.8,
propuestas documentadas nunca decisión 37.9/41.9, comparación What-If
37.11, rechazo de escenarios incompletos 37.21 y auditoría 37.23.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import simulation_api

BASE = {
    "escenario_id": "planta-actual", "descripcion": "Configuración actual",
    "hipotesis": "demanda FDG estable",
    "recursos": [
        {"recurso_id": "cyclo-1", "tipo": "ciclotron", "unidades": 1,
         "horas_disponibles_dia": 8.0, "disponibilidad": 0.9},
        {"recurso_id": "synth-1", "tipo": "modulo_sintesis", "unidades": 1,
         "horas_disponibles_dia": 8.0, "disponibilidad": 0.95},
        {"recurso_id": "qc-lab-1", "tipo": "laboratorio_qc", "unidades": 1,
         "horas_disponibles_dia": 10.0, "disponibilidad": 0.98}],
    "etapas": [
        {"nombre": "irradiacion", "recurso_id": "cyclo-1",
         "duracion_min": 60.0},
        {"nombre": "sintesis", "recurso_id": "synth-1",
         "duracion_min": 45.0},
        {"nombre": "control_calidad", "recurso_id": "qc-lab-1",
         "duracion_min": 30.0}],
    "demanda_diaria_lotes": 6.0, "version": "esc-1.0.0"}


@pytest.fixture()
def client() -> TestClient:
    simulation_api.init()
    c = TestClient(app)
    assert c.post("/api/v1/simulation/scenarios",
                  json=BASE).status_code == 201
    return c


def test_capacity_analyzer_aritmetica_exacta(client: TestClient) -> None:
    r = client.post("/api/v1/simulation/scenarios/planta-actual/run",
                    json={"usuario": "planif-1"})
    assert r.status_code == 201
    res = r.json()
    recs = {x["recurso_id"]: x for x in res["recursos"]}
    # ciclotrón: 1 · 8 · 0.9 · 60/60 = 7.2 lotes/día
    assert recs["cyclo-1"]["capacidad_lotes_dia"] == pytest.approx(7.2)
    # síntesis: 8·0.95·60/45 = 10.1333
    assert recs["synth-1"]["capacidad_lotes_dia"] == pytest.approx(
        8 * 0.95 * 60 / 45, rel=1e-4)
    # rendimiento del proceso = mínimo entre etapas
    assert res["rendimiento_lotes_dia"] == pytest.approx(7.2)
    # utilización del cuello: 6/7.2
    assert recs["cyclo-1"]["utilizacion"] == pytest.approx(6.0 / 7.2, rel=1e-3)
    assert res["cubre_demanda"] is True


def test_bottleneck_detector(client: TestClient) -> None:
    res = client.post("/api/v1/simulation/scenarios/planta-actual/run",
                      json={}).json()
    assert res["cuello_de_botella"]["recurso_id"] == "cyclo-1"
    assert res["cuello_de_botella"]["etapa_limitante"] == "irradiacion"


def test_escenarios_nunca_sobrescriben(client: TestClient) -> None:
    r = client.post("/api/v1/simulation/scenarios", json=BASE)
    assert r.status_code == 422
    lista = client.get("/api/v1/simulation/scenarios").json()
    assert len(lista) == 1 and lista[0]["version"] == "esc-1.0.0"


def test_validacion_rechaza_escenarios_incompletos(client: TestClient) -> None:
    # etapa que referencia recurso inexistente
    malo = {**BASE, "escenario_id": "malo-1",
            "etapas": [{"nombre": "x", "recurso_id": "fantasma",
                        "duracion_min": 10.0}]}
    r = client.post("/api/v1/simulation/scenarios", json=malo)
    assert r.status_code == 422
    # disponibilidad inventada (fuera de rango): rechazada
    malo2 = {**BASE, "escenario_id": "malo-2",
             "recursos": [dict(BASE["recursos"][0], disponibilidad=0.0)]}
    r2 = client.post("/api/v1/simulation/scenarios", json=malo2)
    assert r2.status_code == 422
    assert "ALME" in r2.json()["detail"]
    # sin etapas
    malo3 = {**BASE, "escenario_id": "malo-3", "etapas": []}
    assert client.post("/api/v1/simulation/scenarios",
                       json=malo3).status_code == 422


def test_whatif_duplicar_ciclotrones_duplica_rendimiento(
        client: TestClient) -> None:
    exp = {**BASE, "escenario_id": "expansion-2cyc",
           "descripcion": "Segundo ciclotrón",
           "hipotesis": "expansión 37.10", "version": "esc-1.0.0",
           "recursos": [dict(BASE["recursos"][0], unidades=2),
                        *BASE["recursos"][1:]]}
    assert client.post("/api/v1/simulation/scenarios",
                       json=exp).status_code == 201
    r = client.post("/api/v1/simulation/compare", json={
        "base": "planta-actual", "alternativo": "expansion-2cyc",
        "usuario": "planif-1"})
    comp = r.json()
    assert comp["rendimiento_base"] == pytest.approx(7.2)
    # con 2 ciclotrones (14.4) el cuello pasa a síntesis
    assert comp["rendimiento_alternativo"] == pytest.approx(
        8 * 0.95 * 60 / 45, rel=1e-4)
    assert comp["cuello_base"] == "cyclo-1"
    assert comp["cuello_alternativo"] == "synth-1"
    assert comp["delta_lotes_dia"] > 0
    assert "independientes de la operación" in comp["nota"]


def test_propuesta_es_soporte_no_decision(client: TestClient) -> None:
    r = client.post("/api/v1/simulation/scenarios/planta-actual/propose",
                    json={"usuario": "motor"})
    assert r.status_code == 201
    p = r.json()
    assert p["cuello_de_botella"] == "cyclo-1"
    assert "PROPUESTA" in p["naturaleza"]
    assert "41.9" in p["naturaleza"]


def test_resultados_versionados_y_auditoria(client: TestClient) -> None:
    client.post("/api/v1/simulation/scenarios/planta-actual/run", json={})
    client.post("/api/v1/simulation/scenarios/planta-actual/run", json={})
    res = client.get(
        "/api/v1/simulation/scenarios/planta-actual/results").json()
    assert len(res) == 2          # histórico completo 37.20
    aud = client.get("/api/v1/simulation/audit").json()
    assert sum(1 for a in aud
               if a["accion"] == "ejecutar_simulacion") == 2
    assert all(a["fecha"] for a in aud)


def test_simulacion_no_toca_operacion_real(client: TestClient) -> None:
    # el motor es un servicio aislado: no existe estado operacional que
    # pueda ser modificado por las simulaciones (37.3)
    from app.domain.capacity_simulation import CapacitySimulationEngine
    motor = CapacitySimulationEngine()
    assert not hasattr(motor, "inventory")
    assert not hasattr(motor, "schedule")
